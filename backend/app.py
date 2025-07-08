from flask import Flask
from flask_bcrypt import Bcrypt
from routes.auth import auth_bp
from routes.projects import project_bp
from routes.testcases import testcase_bp
from routes.admin import admin_bp
from routes.manager import manager_bp

import os

app = Flask(
    __name__,
    template_folder='../frontend/templates',
    static_folder='../frontend/static'
)

app.secret_key = os.getenv("SECRET_KEY", "supersecret")
bcrypt = Bcrypt(app)

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(project_bp)
app.register_blueprint(testcase_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(manager_bp)

if __name__ == '__main__':
    app.run(debug=True)
