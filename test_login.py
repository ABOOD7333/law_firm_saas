import requests
import re
import sys
sys.stdout.reconfigure(encoding='utf-8')

session = requests.Session()
url = 'https://web-production-80e9e.up.railway.app/'

res_get = session.get(url)
csrf_cookie = session.cookies.get('csrf_token')

data = {
    'email': 'ABOOD',
    'password': 'admin123456',
    'csrf_token': csrf_cookie
}
headers = {'X-CSRF-Token': csrf_cookie}

res_post = session.post(url, data=data, headers=headers, allow_redirects=False)

print('POST Status:', res_post.status_code)
if res_post.status_code in [302, 303]:
    print('Redirected to:', res_post.headers.get('Location'))
elif res_post.status_code == 500:
    print('Error 500 occurred!')
    print(res_post.text[:1000])
else:
    print('HTML length:', len(res_post.text))
    # Look for the error message in the login HTML
    matches = re.findall(r'<div[^>]*class=["\'][^"\']*alert error[^"\']*["\'][^>]*>(.*?)</div>', res_post.text, re.IGNORECASE | re.DOTALL)
    print('Errors:', matches)
