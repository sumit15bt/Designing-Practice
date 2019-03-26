from flask import Flask
from flask.ext.login import LoginManager
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.bcrypt import Bcrypt
from account_verification_flask.config import config_env_files

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()


def create_app(config_name='development', p_db=db, p_bcrypt=bcrypt, p_login_manager=login_manager):
    new_app = Flask(__name__)
    new_app.config.from_object(config_env_files[config_name])

    p_db.init_app(new_app)
    p_bcrypt.init_app(new_app)
    p_login_manager.init_app(new_app)
    p_login_manager.login_view = 'register'
    return new_app


app = create_app()

import account_verification_flask.views

class DefaultConfig(object):
    SECRET_KEY = '%^!@@*!&$8xdfdirunb52438#(&^874@#^&*($@*(@&^@)(&*)Y_)((+'
    SQLALCHEMY_DATABASE_URI = 'sqlite://'


class DevelopmentConfig(DefaultConfig):
    AUTHY_KEY = 'your_authy_key'

    TWILIO_ACCOUNT_SID = 'your_twilio_account_sid'
    TWILIO_AUTH_TOKEN = 'your_twilio_auth_token'
    TWILIO_NUMBER = 'your_twilio_phone_number'

    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    DEBUG = True


class TestConfig(DefaultConfig):
    SQLALCHEMY_ECHO = True

    DEBUG = True
    TESTING = True
    WTF_CSRF_ENABLED = False


config_env_files = {
    'test': 'account_verification_flask.config.TestConfig',
    'development': 'account_verification_flask.config.DevelopmentConfig',
}



# from flask.ext.login import UserMixin
from account_verification_flask import db, bcrypt


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False)
    password = db.Column(db.String)
    phone_number = db.Column(db.String, nullable=False)
    country_code = db.Column(db.String, nullable=False)
    phone_number_confirmed = db.Column(db.Boolean, nullable=False, default=False)
    authy_user_id = db.Column(db.String, nullable=True)

    def __init__(self, name, email, password, phone_number, country_code):
        self.name = name
        self.email = email
        self.password = bcrypt.generate_password_hash(password)
        self.phone_number = phone_number
        self.country_code = country_code
        self.phone_number_confirmed = False

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return unicode(self.id)

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return '<User %r>' % (self.name)
	


@app.route('/verify', methods=["GET", "POST"])
@app.route('/verify/<email>', methods=["GET"])
def verify():
    form = VerifyCodeForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            user = User.query.filter(User.email == form.email.data).first()

            if user == None:
                form.email.errors.append(account_verification_flask.utilities.User_Not_Found_For_Given_Email)
                return view('verify_registration_code', form)

            if user.phone_number_confirmed:
                form.email.errors.append(User_Already_Confirmed)
                return view('verify_registration_code', form)

            authy_services = AuthyServices()
            if authy_services.confirm_phone_number(user, form.verification_code.data):
                user.phone_number_confirmed = True
                db.session.commit()
                login_user(user, remember=True)
                twilio_services = TwilioServices()
                twilio_services.send_registration_success_sms("+{0}{1}".format(user.country_code, user.phone_number))
                return redirect_to('status')
            else:
                form.email.errors.append(account_verification_flask.utilities.Verification_Unsuccessful)
                return view('verify_registration_code', form)
    else:
        form.email.data = request.args.get('email')
    return view('verify_registration_code', form)





@app.route('/resend', methods=["GET", "POST"])
@app.route('/resend/<email>', methods=["GET"])
def resend(email=""):
    form = ResendCodeForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            user = User.query.filter(User.email == form.email.data).first()

            if user == None:
                form.email.errors.append(account_verification_flask.utilities.User_Not_Found_For_Given_Email)
                return view('resend_confirmation_code', form)

            if user.phone_number_confirmed:
                form.email.errors.append(account_verification_flask.utilities.User_Already_Confirmed)
                return view('resend_confirmation_code', form)
            authy_services = AuthyServices()
            if authy_services.request_phone_confirmation_code(user):
                flash(account_verification_flask.utilities.Verification_Code_Resent)
                return redirect_to('verify', email=form.email.data)
            else:
                form.email.errors.append(account_verification_flask.utilities.Verification_Code_Not_Sent)
    else:
        form.email.data = email

    return view('resend_confirmation_code', form)



def request_phone_confirmation_code(self, user):
        if user == None:
            raise ValueError(account_verification_flask.utilities.User_Id_Not_Found)

        if user.authy_user_id == None:
            self._register_user_under_authy(user)

        sms = AuthyServices.authy_client.users.request_sms(user.authy_user_id, {'force': True})
        return not sms.ignored()	


 def confirm_phone_number(self, user, verification_code):
        if user == None:
            raise ValueError(account_verification_flask.utilities.User_Id_Not_Found)

        verification = AuthyServices.authy_client.tokens.verify(user.authy_user_id, verification_code)
        return verification.ok()


import account_verification_flask.utilities
from account_verification_flask.utilities.settings import TwilioSettings
from twilio.rest import Client


class TwilioServices:
    twilio_client = None

    def __init__(self):
        if TwilioServices.twilio_client == None:
            TwilioServices.twilio_client = Client(TwilioSettings.account_sid(), TwilioSettings.auth_token())

    def send_registration_success_sms(self, to_number):
        message = TwilioServices.twilio_client.messages.create(
            body=account_verification_flask.utilities.Signup_Complete,
            to=to_number,
            from_=TwilioSettings.phone_number())





{% extends "layout.html" %}

{% block content %}

<h1>We're going to be *BEST* friends</h1>
<p> Thanks for your interest in signing up! Can you tell us a bit about yourself?</p>


<form method="POST" class="form-horizontal" role="form">
    {% from "_formhelpers.html" import render_errors, render_field %}
    {{ form.csrf_token }}
    {{ render_errors(form) }}
    <hr/>

    {{ render_field(form.name, placeholder='Anakin Skywalker') }}
    {{ render_field(form.email, placeholder='darth@vader.com') }}
    {{ render_field(form.password) }}
    {{ render_field(form.country_code, id="authy-countries" ) }}
    {{ render_field(form.phone_number , type='number') }}

    <div class="form-group">
        <div class="col-md-offset-2 col-md-10">
            <input type="submit" class="btn btn-primary" value="Sign Up" />
        </div>
    </div>
</form>

{% endblock %}


def register():
    form = RegisterForm()
    if request.method == 'POST':
        if form.validate_on_submit():

            if User.query.filter(User.email == form.email.data).count() > 0:
                form.email.errors.append(account_verification_flask.utilities.User_Email_Already_In_Use)
                return view('register', form)

            user = User(
                name=form.name.data,
                email=form.email.data,
                password=form.password.data,
                country_code=form.country_code.data,
                phone_number=form.phone_number.data
            )
            db.session.add(user)
            db.session.commit()

            authy_services = AuthyServices()
            if authy_services.request_phone_confirmation_code(user):
                db.session.commit()
                flash(account_verification_flask.utilities.Verification_Code_Sent)
                return redirect_to('verify', email=form.email.data)

            form.email.errors.append(account_verification_flask.utilities.Verification_Code_Not_Sent)

        else:
            return view('register', form)

    return view('register', form)







