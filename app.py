from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from enum import Enum
import os
import uuid
import google.generativeai as genai

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///medical.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'your-secret-key-here'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=30)

db = SQLAlchemy(app)
jwt = JWTManager(app)
CORS(app)

genai.configure(api_key='YOUR_GEMINI_API_KEY')
model = genai.GenerativeModel('gemini-2.5-flash')

# ============================================================================
# ENUMS
# ============================================================================

class AppointmentStatus(Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

# ============================================================================
# DATABASE MODELS
# ============================================================================

class Patient(db.Model):
    __tablename__ = 'patients'
    id = db.Column(db.String(20), primary_key=True, default=lambda: str(uuid.uuid4())[:20])
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    date_of_birth = db.Column(db.Date)
    address = db.Column(db.String(255))
    blood_group = db.Column(db.String(5))
    medical_history = db.Column(db.Text)
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    appointments = db.relationship('Appointment', backref='patient', lazy=True, cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref='patient', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'email': self.email,
            'phone': self.phone
        }

class Doctor(db.Model):
    __tablename__ = 'doctors'
    id = db.Column(db.String(20), primary_key=True, default=lambda: str(uuid.uuid4())[:20])
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    specialization = db.Column(db.String(50), nullable=False)
    license_number = db.Column(db.String(50), unique=True, nullable=False)
    consultation_fee = db.Column(db.Float, default=500.0)
    experience_years = db.Column(db.Integer, default=0)
    bio = db.Column(db.Text)
    rating_average = db.Column(db.Float, default=0.0)
    is_available = db.Column(db.Boolean, default=True)
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    time_slots = db.relationship('TimeSlot', backref='doctor', lazy=True, cascade='all, delete-orphan')
    appointments = db.relationship('Appointment', backref='doctor', lazy=True, cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref='doctor', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'email': self.email,
            'specialization': self.specialization,
            'consultation_fee': self.consultation_fee,
            'experience_years': self.experience_years,
            'rating_average': round(self.rating_average, 2),
            'is_available': self.is_available,
            'bio': self.bio
        }

class TimeSlot(db.Model):
    __tablename__ = 'time_slots'
    id = db.Column(db.String(20), primary_key=True, default=lambda: str(uuid.uuid4())[:20])
    doctor_id = db.Column(db.String(20), db.ForeignKey('doctors.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    is_available = db.Column(db.Boolean, default=True)
    capacity = db.Column(db.Integer, default=1)
    booked_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'doctor_id': self.doctor_id,
            'date': self.date.isoformat(),
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'is_available': self.is_available
        }

class Appointment(db.Model):
    __tablename__ = 'appointments'
    id = db.Column(db.String(20), primary_key=True, default=lambda: str(uuid.uuid4())[:20])
    patient_id = db.Column(db.String(20), db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.String(20), db.ForeignKey('doctors.id'), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), default=AppointmentStatus.PENDING.value)
    consultation_notes = db.Column(db.Text)
    ai_recommendation = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    reviews = db.relationship('Review', backref='appointment', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'doctor_id': self.doctor_id,
            'appointment_date': self.appointment_date.isoformat(),
            'appointment_time': self.appointment_time.isoformat(),
            'status': self.status,
            'consultation_notes': self.consultation_notes,
            'ai_recommendation': self.ai_recommendation
        }

class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.String(20), primary_key=True, default=lambda: str(uuid.uuid4())[:20])
    patient_id = db.Column(db.String(20), db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.String(20), db.ForeignKey('doctors.id'), nullable=False)
    appointment_id = db.Column(db.String(20), db.ForeignKey('appointments.id'))
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ============================================================================
# AUTH ROUTES
# ============================================================================

@app.route('/api/auth/patient-register', methods=['POST'])
def patient_register():
    data = request.json
    if not all(key in data for key in ['first_name', 'last_name', 'email', 'phone', 'password']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    if Patient.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 400
    
    patient = Patient(
        first_name=data['first_name'],
        last_name=data['last_name'],
        email=data['email'],
        phone=data['phone']
    )
    patient.set_password(data['password'])
    
    db.session.add(patient)
    db.session.commit()
    
    access_token = create_access_token(identity=patient.id)
    return jsonify({
        'message': 'Patient registered successfully',
        'access_token': access_token,
        'patient': patient.to_dict()
    }), 201

@app.route('/api/auth/patient-login', methods=['POST'])
def patient_login():
    data = request.json
    patient = Patient.query.filter_by(email=data['email']).first()
    
    if not patient or not patient.check_password(data['password']):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    access_token = create_access_token(identity=patient.id)
    return jsonify({
        'access_token': access_token,
        'patient': patient.to_dict()
    }), 200

@app.route('/api/auth/doctor-register', methods=['POST'])
def doctor_register():
    data = request.json
    required = ['first_name', 'last_name', 'email', 'phone', 'password', 'specialization', 'license_number']
    if not all(key in data for key in required):
        return jsonify({'error': 'Missing required fields'}), 400
    
    if Doctor.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 400
    
    doctor = Doctor(
        first_name=data['first_name'],
        last_name=data['last_name'],
        email=data['email'],
        phone=data['phone'],
        specialization=data['specialization'],
        license_number=data['license_number'],
        consultation_fee=data.get('consultation_fee', 500.0)
    )
    doctor.set_password(data['password'])
    
    db.session.add(doctor)
    db.session.commit()
    
    access_token = create_access_token(identity=doctor.id)
    return jsonify({
        'message': 'Doctor registered successfully',
        'access_token': access_token,
        'doctor': doctor.to_dict()
    }), 201

@app.route('/api/auth/doctor-login', methods=['POST'])
def doctor_login():
    data = request.json
    doctor = Doctor.query.filter_by(email=data['email']).first()
    
    if not doctor or not doctor.check_password(data['password']):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    access_token = create_access_token(identity=doctor.id)
    return jsonify({
        'access_token': access_token,
        'doctor': doctor.to_dict()
    }), 200

# ============================================================================
# DOCTOR ROUTES
# ============================================================================

@app.route('/api/doctors', methods=['GET'])
def get_doctors():
    specialization = request.args.get('specialization')
    query = Doctor.query.filter_by(is_available=True)
    if specialization:
        query = query.filter_by(specialization=specialization)
    
    doctors = query.all()
    return jsonify({
        'doctors': [d.to_dict() for d in doctors],
        'count': len(doctors)
    }), 200

@app.route('/api/doctors/<doctor_id>', methods=['GET'])
def get_doctor(doctor_id):
    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        return jsonify({'error': 'Doctor not found'}), 404
    return jsonify(doctor.to_dict()), 200

@app.route('/api/doctors/<doctor_id>/available-slots', methods=['GET'])
def get_available_slots(doctor_id):
    date = request.args.get('date')
    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        return jsonify({'error': 'Doctor not found'}), 404
    
    query = TimeSlot.query.filter_by(doctor_id=doctor_id, is_available=True)
    if date:
        query = query.filter_by(date=date)
    
    slots = query.all()
    return jsonify({
        'slots': [s.to_dict() for s in slots],
        'count': len(slots)
    }), 200

@app.route('/api/doctors/<doctor_id>/add-slots', methods=['POST'])
@jwt_required()
def add_time_slots(doctor_id):
    data = request.json
    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        return jsonify({'error': 'Doctor not found'}), 404
    
    slot = TimeSlot(
        doctor_id=doctor_id,
        date=data['date'],
        start_time=data['start_time'],
        end_time=data['end_time'],
        capacity=data.get('capacity', 1)
    )
    
    db.session.add(slot)
    db.session.commit()
    
    return jsonify({
        'message': 'Time slot added successfully',
        'slot': slot.to_dict()
    }), 201

# ============================================================================
# APPOINTMENT ROUTES
# ============================================================================

@app.route('/api/appointments', methods=['POST'])
@jwt_required()
def book_appointment():
    data = request.json
    patient_id = get_jwt_identity()
    
    patient = Patient.query.get(patient_id)
    doctor = Doctor.query.get(data['doctor_id'])
    
    if not patient or not doctor:
        return jsonify({'error': 'Patient or Doctor not found'}), 404
    
    appointment = Appointment(
        patient_id=patient_id,
        doctor_id=data['doctor_id'],
        appointment_date=data['appointment_date'],
        appointment_time=data['appointment_time'],
        consultation_notes=data.get('consultation_notes')
    )
    
    db.session.add(appointment)
    db.session.commit()
    
    return jsonify({
        'message': 'Appointment booked successfully',
        'appointment': appointment.to_dict()
    }), 201

@app.route('/api/appointments/<appointment_id>', methods=['GET'])
def get_appointment(appointment_id):
    appointment = Appointment.query.get(appointment_id)
    if not appointment:
        return jsonify({'error': 'Appointment not found'}), 404
    return jsonify(appointment.to_dict()), 200

@app.route('/api/appointments/patient/<patient_id>', methods=['GET'])
@jwt_required()
def get_patient_appointments(patient_id):
    status = request.args.get('status')
    query = Appointment.query.filter_by(patient_id=patient_id)
    if status:
        query = query.filter_by(status=status)
    
    appointments = query.all()
    return jsonify({
        'appointments': [a.to_dict() for a in appointments],
        'count': len(appointments)
    }), 200

@app.route('/api/appointments/<appointment_id>/cancel', methods=['PUT'])
@jwt_required()
def cancel_appointment(appointment_id):
    appointment = Appointment.query.get(appointment_id)
    if not appointment:
        return jsonify({'error': 'Appointment not found'}), 404
    
    appointment.status = AppointmentStatus.CANCELLED.value
    appointment.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({
        'message': 'Appointment cancelled successfully',
        'appointment': appointment.to_dict()
    }), 200

@app.route('/api/appointments/<appointment_id>/confirm', methods=['PUT'])
@jwt_required()
def confirm_appointment(appointment_id):
    appointment = Appointment.query.get(appointment_id)
    if not appointment:
        return jsonify({'error': 'Appointment not found'}), 404
    
    appointment.status = AppointmentStatus.CONFIRMED.value
    db.session.commit()
    
    return jsonify({
        'message': 'Appointment confirmed',
        'appointment': appointment.to_dict()
    }), 200

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("✅ Database initialized!")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
