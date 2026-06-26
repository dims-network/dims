#!/usr/bin/env python3
"""
Local dev server with HTTP Range request support (required for video seeking).
Usage: python serve.py [port]
"""
import http.server
import os
import sys


class RangeRequestHandler(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        path = self.translate_path(self.path.split('?')[0])

        if not os.path.isfile(path):
            return super().send_head()

        range_header = self.headers.get('Range')
        if not range_header:
            return super().send_head()

        size = os.path.getsize(path)
        try:
            byte_range = range_header.strip().removeprefix('bytes=')
            start_str, end_str = byte_range.split('-')
            start = int(start_str)
            end = int(end_str) if end_str else size - 1
        except (ValueError, AttributeError):
            self.send_error(400, 'Bad Range header')
            return None

        end = min(end, size - 1)
        length = end - start + 1

        f = open(path, 'rb')
        f.seek(start)

        self.send_response(206)
        self.send_header('Content-Type', self.guess_type(path))
        self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.send_header('Content-Length', str(length))
        self.send_header('Accept-Ranges', 'bytes')
        self.end_headers()
        return f

    def log_message(self, fmt, *args):
        # Suppress noisy request logs; only show errors
        if args and str(args[1]) not in ('200', '206', '304'):
            super().log_message(fmt, *args)


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = http.server.HTTPServer(('', port), RangeRequestHandler)
    print(f'Serving on http://localhost:{port}')
    server.serve_forever()
