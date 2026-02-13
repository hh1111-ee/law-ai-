from http.server import SimpleHTTPRequestHandler, HTTPServer
import os

class MyHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # 将网站根目录设置为 html 文件夹
        super().__init__(*args, directory=os.path.join(os.getcwd(), 'html'), **kwargs)
    def do_GET(self):
        if self.path == '/':
            self.path = '/主页.html'  # 把这里改成你的实际首页文件名
        return super().do_GET()
if __name__ == '__main__':
    server_address = ('0.0.0.0', 5501)
    httpd = HTTPServer(server_address, MyHandler)
    print("服务器运行在 http://localhost:5501，网站根目录为 'html' 文件夹")
    httpd.serve_forever()