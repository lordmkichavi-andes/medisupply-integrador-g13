from flask import Flask, jsonify, request, make_response
from functools import wraps
import os
import json



app = Flask(__name__)



@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
