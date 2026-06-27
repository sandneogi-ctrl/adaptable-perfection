import os
from flask import Flask, jsonify
from flask_cors import CORS
from routes.stocks import stocks_bp

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
app.register_blueprint(stocks_bp)

@app.route('/')
def home():
    return jsonify({"status": "ok", "message": "Nifty50 Scanner API"})

@app.route('/api/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
