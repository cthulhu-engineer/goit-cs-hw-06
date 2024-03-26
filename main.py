import logging
import mimetypes
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from multiprocessing import Process
from pathlib import Path
from urllib.parse import urlparse, unquote_plus
from pymongo import MongoClient
from datetime import datetime

# Configuration
config = {
    "mongo_uri": "mongodb://mongodb:27017/",
    "base_dir": Path(__file__).parent,
    "http_host": '0.0.0.0',
    "http_port": 3000,
    "socket_host": '127.0.0.1',
    "socket_port": 5000,
    "buffer_size": 1024,
}

# HTTP Status Codes
HTTP_NOT_FOUND = 404
HTTP_SERVER_ERROR = 500


class SimpleFramework(BaseHTTPRequestHandler):
    """A simple framework for handling HTTP requests.

        This class inherits from BaseHTTPRequestHandler and implements methods for handling both GET and POST
        requests. It provides functionality for sending HTML files, sending other files *, forwarding data to a
        socket, and redirecting to a different path.

        Methods:
            do_GET(self)
            do_POST(self)
            send_html(self, filename, status=200)
            send_file(self, filepath, status=200)
            forward_to_socket(self, data)
            redirect(self, path)
        """
    def do_GET(self):
        router = urlparse(self.path).path
        if router == "/":
            self.send_html("index.html")
        elif router == "/message":
            self.send_html("message.html")
        else:
            file_path = config["base_dir"].joinpath(router.lstrip("/"))
            self.send_file(file_path)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(content_length)
        self.forward_to_socket(data)
        self.redirect("/")

    def send_html(self, filename, status=200):
        self.send_file(config["base_dir"].joinpath(filename), status)

    def send_file(self, filepath, status=200):
        if filepath.exists():
            self.send_response(status)
            mimetype = mimetypes.guess_type(filepath)[0] or "text/plain"
            self.send_header("Content-type", mimetype)
            self.end_headers()
            with open(filepath, "rb") as file:
                self.wfile.write(file.read())
        else:
            self.send_html("error.html", HTTP_NOT_FOUND)

    def forward_to_socket(self, data):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
            client_socket.sendto(data, (config["socket_host"], config["socket_port"]))

    def redirect(self, path):
        self.send_response(302)
        self.send_header("Location", path)
        self.end_headers()


def save_data(data):
    """
    Save data to the MongoDB database.

    :param data: The data to be saved.
    :return: None
    """
    with MongoClient(config["mongo_uri"]) as client:
        db = client.final_home_work
        data_str = unquote_plus(data.decode())
        try:
            data_dict = dict(kv.split("=") for kv in data_str.split("&"))
            data_dict["date"] = datetime.now()
            db.messages.insert_one(data_dict)
        except Exception as e:
            logging.error(f"Failed to save data: {e}")


def run_http_server():
    """
    Run the HTTP server.

    :return: None
    """
    server_address = (config["http_host"], config["http_port"])
    httpd = HTTPServer(server_address, SimpleFramework)
    logging.info(f"HTTP Server running at http://{config['http_host']}:{config['http_port']}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        logging.info("HTTP Server stopped.")


def run_socket_server():
    """
    Runs a socket server that listens for incoming data and saves it.

    :return: None
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((config["socket_host"], config["socket_port"]))
        logging.info(f"Socket Server running at socket://{config['socket_host']}:{config['socket_port']}")
        try:
            while True:
                data, _ = sock.recvfrom(config["buffer_size"])
                logging.info("Data received via socket.")
                save_data(data)
        except KeyboardInterrupt:
            pass
        finally:
            logging.info("Socket Server stopped.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    http_process = Process(target=run_http_server)
    socket_process = Process(target=run_socket_server)
    http_process.start()
    socket_process.start()

    http_process.join()
    socket_process.join()
