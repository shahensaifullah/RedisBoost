# 🚀 Django + PostgreSQL + Redis Cache Project


### 💡 Key Concepts

- **PostgreSQL** is the main data source (source of truth)
- **Redis** acts as a caching layer for faster reads
- **Django REST API** retrieves and serves data from Redis
- **Search functionality** can be performed on cached data

---

## 🧱 Tech Stack

- **Django** 6  
- **Python** 3.12+  
- **PostgreSQL**  
- **Redis Stack Server**  
- **Docker**  
- **Docker Compose**

---

## ⚙️ Setup Instructions

### 1. Run Redis and PostgreSQL using Docker

You can spin up both Redis and PostgreSQL using Docker Compose:

```bash
docker compose up -d
```

This will start:

- PostgreSQL  
- Redis Stack Server  

📘 **Redis Stack Installation Guide:**  
[Redis Stack Installation Docs](https://redis.io/docs/latest/operate/oss_and_stack/install/archive/install-stack/)

---

### 2. Install Python and Dependencies

Make sure you have **Python 3.12 or higher** installed, then install the required dependencies:

```bash
pip install -r requirements.txt
```

---

### 3. Run Data Sync Command

Execute the custom Django management command to sync all data between PostgreSQL and Redis:

```bash
python manage.py db_and_redis_sync
```

#### 🔄 What This Command Does

1. Runs `makemigrations` and `migrate`  
2. Fetches dataset from **Kaggle**  
3. Saves dataset into the **public folder**  
4. Inserts data into the **PostgreSQL database**  
5. Reads all data from **PostgreSQL**  
6. Saves all processed data into **Redis cache**

---

## 🌐 API Usage

### Endpoint

```http
GET /products
```

### Behavior

- Retrieves data **directly from Redis cache**  
- Provides **faster responses** than PostgreSQL queries  
- Supports **search functionality** on cached data  

---

## ⚡ Summary

By integrating **Redis Stack**, **PostgreSQL**, and **Django**, this setup achieves:
- Reduced database load
- Improved query performance
- Enhanced scalability for data-intensive applications