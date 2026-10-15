import sys
import os
import time
import uuid
import secrets
from PIL import Image
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, url_for, jsonify

# Add project root directory to sys.path so 'scripts' module can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from algo_interface import ALGORITHM_MODULES

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['OUTPUT_FOLDER'] = os.path.join(app.root_path, 'static', 'output')

# Production Configuration: Max upload limit (default 16MB) and session secret key
max_mb = int(os.environ.get('MAX_CONTENT_LENGTH_MB', '16'))
app.config['MAX_CONTENT_LENGTH'] = max_mb * 1024 * 1024
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Ensure folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)


def cleanup_old_files(max_age_seconds=None):
    """Periodically removes orphaned uploads and generated shares older than max_age_seconds."""
    if max_age_seconds is None:
        max_age_seconds = int(os.environ.get('FILE_CLEANUP_MAX_AGE_SECONDS', '3600'))
    now = time.time()
    for folder in [app.config['UPLOAD_FOLDER'], app.config['OUTPUT_FOLDER']]:
        try:
            for entry in os.scandir(folder):
                if entry.is_file() and entry.name != '.gitkeep':
                    try:
                        if now - entry.stat().st_mtime > max_age_seconds:
                            os.remove(entry.path)
                    except OSError:
                        pass
        except Exception:
            pass


# Route for health monitoring (for Docker, Kubernetes, Render, Railway, AWS ECS)
@app.route('/health', methods=['GET'])
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "service": "VisualCrypto",
        "algorithms_loaded": len(ALGORITHM_MODULES)
    }), 200


# Error Handlers for Production
@app.errorhandler(413)
def request_entity_too_large(error):
    return render_template('error.html', error_message=f"File exceeds maximum upload limit of {max_mb} MB."), 413


@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', error_message="Requested resource not found."), 404


@app.errorhandler(500)
def internal_server_error(error):
    return render_template('error.html', error_message="An internal server error occurred while processing."), 500


# Route for the main page
@app.route('/')
def home():
    return render_template('index.html')


# Route that returns the list of algorithms available
@app.route('/api/algorithm_list', methods=['GET'])
def get_algorithms():
    algorithms = {key: value["name"] for key, value in ALGORITHM_MODULES.items()}  # Extract key and name
    return jsonify({"algorithms": algorithms})


# Route that returns the description of the indicated algorithm
@app.route('/api/algorithm_description/<algorithm>')
def get_algorithm_description(algorithm):
    module = ALGORITHM_MODULES.get(algorithm)
    if module and "description" in module:
        return jsonify(module["description"])

    return jsonify({"text": "Description not available.", "links": []})


# Route that returns the requirements of the indicated algorithm
@app.route('/api/algorithm_requirements/<algorithm>/<operation>', methods=['GET'])
def get_algorithm_requirements(algorithm, operation):
    try:
        # Check if the requested algorithm exists
        if algorithm not in ALGORITHM_MODULES:
            return jsonify({"error": "Algorithm not found"}), 404

        # Retrieve the algorithm's requirements
        requirements = ALGORITHM_MODULES[algorithm].get("requirements", {})

        # Check if the requested operation (encryption/decryption) exists
        if operation not in requirements:
            return jsonify({"error": "Invalid operation"}), 400

        # Extract the required number of input images and parameters
        operation_requirements = requirements[operation]
        num_images = operation_requirements.get("num_images", 1)
        parameters = operation_requirements.get("parameters", {})

        # Return the JSON response
        return jsonify({
            "num_images": num_images,
            "parameters": parameters
        })

    except Exception as e:
        print("Error:", str(e))
        return jsonify({"error": str(e)}), 500


# Process the selected operation
@app.route('/process', methods=['POST'])
def process():
    try:
        # Periodically clean up stale files
        cleanup_old_files()

        operation = request.form['operation']
        algorithm = request.form['algorithm']

        # Retrieve the algorithm module
        algorithm_module = ALGORITHM_MODULES.get(algorithm)
        if not algorithm_module:
            error_message = f"Unknown algorithm: {algorithm}"
            return render_template('error.html', error_message=error_message), 500

        # Retrieve algorithm requirements for the operation
        requirements = algorithm_module.get("requirements", {}).get(operation, {})
        num_images = requirements.get("num_images", 1)
        parameters = requirements.get("parameters", {})

        # Unique batch ID for this operation to isolate concurrent requests
        batch_id = uuid.uuid4().hex[:10]

        # Dynamically retrieve uploaded images based on num_images
        input_paths = []
        for i in range(1, num_images + 1):
            file = request.files.get(f"image{i}")
            if file and file.filename:
                safe_name = secure_filename(file.filename) or f"input_{i}.png"
                unique_filename = f"{batch_id}_in_{i}_{safe_name}"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(save_path)
                input_paths.append(save_path)

        # Ensure correct number of images
        if len(input_paths) != num_images:
            error_message = f"{operation.capitalize()} requires {num_images} image(s), but {len(input_paths)} provided."
            return render_template('error.html', error_message=error_message), 500

        # Open images
        images = [Image.open(path).convert(algorithm_module.get("image_type")) for path in input_paths]

        # Extract additional parameters from the form
        param_values = {}
        for param_key, param_config in parameters.items():
            if param_config["type"] == "number":
                param_values[param_key] = int(request.form.get(param_key, param_config.get("default", 0)))
            elif param_config["type"] == "select":
                param_values[param_key] = request.form.get(param_key, param_config.get("default"))

        # Call the appropriate method dynamically
        if operation == "encryption":
            encrypt_method = algorithm_module.get("encrypt")
            result = encrypt_method(*images, *param_values.values())
            return save_and_render_shares(*result, batch_id=batch_id, extension=algorithm_module.get("extension"))

        elif operation == "decryption":
            decrypt_method = algorithm_module.get("decrypt")
            result = decrypt_method(*images, *param_values.values())
            return save_and_render_decryption_result(result, batch_id=batch_id, extension=algorithm_module.get("extension"))

    except Exception as e:
        error_message = str(e)
        return render_template('error.html', error_message=error_message), 500


def save_and_render_shares(*shares, batch_id=None, extension='png', output_folder='output'):
    if batch_id is None:
        batch_id = uuid.uuid4().hex[:10]
    share_urls = []
    download_urls = []

    for i, share in enumerate(shares, start=1):
        filename = f"{batch_id}_share{i}.{extension}"
        share_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)

        # Save shares
        share.save(share_path)

        # Generate URLs for rendering and downloading
        share_urls.append(url_for('static', filename=f'{output_folder}/{filename}'))
        download_urls.append(url_for('static', filename=f'{output_folder}/{filename}'))

    # Render results dynamically
    return render_template(
        'enc_result.html',
        share_urls=share_urls,
        download_urls=download_urls,
        zip=zip
    )


def save_and_render_decryption_result(result_image, batch_id=None, extension='png', output_folder='output'):
    if batch_id is None:
        batch_id = uuid.uuid4().hex[:10]
    filename = f"{batch_id}_decrypted.{extension}"
    result_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
    result_image.save(result_path)

    # Render results
    return render_template(
        'dec_result.html',
        result_url=url_for('static', filename=f'{output_folder}/{filename}'),
        result_download=url_for('static', filename=f'{output_folder}/{filename}')
    )


if __name__ == '__main__':
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() in ('true', '1', 'yes')
    app.run(host=host, port=port, debug=debug)
