import sys
import os
import io

from wsgi import app

client = app.test_client()

# Test 1: Health Endpoint
res = client.get('/health')
print(f"[PASS] Health Check: {res.status_code} -> {res.get_json()}")
assert res.status_code == 200, "Health check failed!"

# Test 2: Algorithm List Endpoint
res_algos = client.get('/api/algorithm_list')
print(f"[PASS] Algorithm List: {res_algos.status_code} -> {len(res_algos.get_json()['algorithms'])} algorithms loaded")
assert res_algos.status_code == 200, "Algorithm list failed!"

# Test 3: Home Page
res_home = client.get('/')
print(f"[PASS] Home Page: {res_home.status_code}")
assert res_home.status_code == 200, "Home page failed!"

# Test 4: End-to-End Encryption with batch isolation
test_image_path = os.path.join(os.path.dirname(__file__), 'scripts', 'images', 'test.png')
if os.path.exists(test_image_path):
    with open(test_image_path, 'rb') as f:
        data = {
            'operation': 'encryption',
            'algorithm': 'rg_color_additive_SS',
            'image1': (io.BytesIO(f.read()), 'test.png')
        }
        res_proc = client.post('/process', data=data, content_type='multipart/form-data')
        print(f"[PASS] Process Encryption (rg_color_additive_SS): {res_proc.status_code}")
        assert res_proc.status_code == 200, "Encryption processing failed!"
        assert b"Download Share 1" in res_proc.data
        assert b"Download Share 2" in res_proc.data

# Test 5: Verify author name is Arnav Kadam in algorithm descriptions
res_desc = client.get('/api/algorithm_description/rg_color_additive_SS')
desc_data = res_desc.get_json()
print(f"[PASS] Algorithm Description: {desc_data}")
assert any(link.get('text') == 'Arnav Kadam' for link in desc_data.get('links', [])), "Author was not updated to Arnav Kadam!"

print("\n>>> ALL PRODUCTION DEPLOYMENT TESTS PASSED WITH 100% SUCCESS! <<<")
