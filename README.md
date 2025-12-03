# 🏥 Medservise – Medical Clinic Management System

Medservise is a full-featured **medical clinic management system** built with **Django**, **Django REST Framework**, **PostgreSQL**, **Redis**, and **Docker**.  
It provides an end-to-end workflow for clinics, including patient registration, treatment rooms, lab referrals, doctor worklists, billing, and receipt generation.

This project is designed for real-world use and is currently deployed in production.

---

## 🚀 Features

### 👨‍⚕️ **Doctors**
- Daily worklist with patient queue  
- View pending, in-progress, and completed appointments  
- Medical service selection  
- Automatic billing creation after service  
- Lab referral creation  

### 🧑‍🔬 **Laboratory**
- Receive lab requests from doctors  
- Manage test results  
- Update test status (pending → in progress → completed)  

### 🧾 **Billing & Payments**
- Automatic creation of treatment room payments  
- Support for:
  - Cash  
  - Card  
  - Insurance  
  - Bank transfer  
- Receipt generation (HTML / PDF)  
- Patient balance tracking (paid, unpaid, partial)  

### 🏥 **Treatment Room Workflow**
- Select multiple services  
- Auto-calculate total due amount  
- Create lab referrals  
- Save patient history  

### 👤 **User Management**
- JWT authentication (access + refresh tokens)  
- Role-based access:
  - Admin  
  - Doctor  
  - Cashier  
  - Lab technician  

### 📊 **Admin Panel**
- Manage services  
- Manage treatment rooms  
- Manage users and roles  
- View financial data  

---

## 🛠️ Tech Stack

**Backend:**  
- Python  
- Django  
- Django REST Framework (DRF)  
- JWT Authentication  
- Celery (optional)

**Database:**  
- PostgreSQL  
- Redis (caching / sessions)

**DevOps:**  
- Docker  
- Docker Compose  
- Gunicorn + Nginx (production)

**Other:**  
- HTML/JS frontend  
- Swagger API documentation  

---

## 📦 Installation & Setup

### 1️⃣ Clone the repository
```bash
git clone https://github.com/SAI909099/Medservise.git
cd Medservise

2️⃣ Create the .env file
SECRET_KEY=your-secret-key
DB_NAME=medservise
DB_USER=postgres
DB_PASSWORD=yourpassword
DB_HOST=db
DB_PORT=5432

3️⃣ Run with Docker (recommended)
docker-compose up --build

4️⃣ Run database migrations
docker-compose exec web python manage.py migrate

5️⃣ Create admin user
docker-compose exec web python manage.py createsuperuser
```
👨‍💻 Author

Abdulazizxon Sulaymonov
Python Backend Developer
📧 sulaymonovabdulaziz1@gmail.com

GitHub: https://github.com/SAI909099
