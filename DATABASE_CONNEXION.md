# Connexion à PostgreSQL depuis votre code

## 📋 Informations de connexion

```
Host:     localhost
Port:     5432
Database: mydb
Username: postgres
Password: postgres
```

**String de connexion** :
```
postgresql://postgres:postgres@localhost:5432/mydb
```

---

## 🐍 Python

### Installation
```bash
pip install psycopg2-binary python-dotenv
```

### Connexion simple
```python
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="mydb",
    user="postgres",
    password="postgres"
)

cursor = conn.cursor()
cursor.execute("SELECT version();")
result = cursor.fetchone()
print(result)

cursor.close()
conn.close()
```

### Avec variables d'environnement (recommandé)
```python
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv('DB_HOST'),
    port=os.getenv('DB_PORT'),
    database=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD')
)

cursor = conn.cursor()
# Votre code ici
cursor.close()
conn.close()
```

---

## 🟢 Node.js

### Installation
```bash
npm install pg dotenv
```

### Connexion simple
```javascript
const { Client } = require('pg');

const client = new Client({
    host: 'localhost',
    port: 5432,
    database: 'mydb',
    user: 'postgres',
    password: 'postgres'
});

client.connect()
    .then(() => console.log('Connecté'))
    .catch(err => console.error(err));

client.query('SELECT NOW()', (err, res) => {
    console.log(res.rows);
    client.end();
});
```

### Avec Pool (recommandé pour production)
```javascript
const { Pool } = require('pg');

const pool = new Pool({
    host: 'localhost',
    port: 5432,
    database: 'mydb',
    user: 'postgres',
    password: 'postgres',
    max: 20
});

// Exécuter une requête
pool.query('SELECT NOW()', (err, res) => {
    if (err) throw err;
    console.log(res.rows);
});
```

### Avec variables d'environnement (recommandé)
```javascript
require('dotenv').config();
const { Pool } = require('pg');

const pool = new Pool({
    host: process.env.DB_HOST,
    port: process.env.DB_PORT,
    database: process.env.DB_NAME,
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD
});

// Votre code ici
```

---

## ⚙️ Configuration avec variables d'environnement

### Créer un fichier .env dans votre projet
```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mydb
DB_USER=postgres
DB_PASSWORD=postgres
```

### Ajouter .env au .gitignore
```bash
echo ".env" >> .gitignore
```

**Pourquoi utiliser des variables d'environnement ?**
- ✅ Ne jamais exposer de mots de passe dans le code
- ✅ Facilite le changement d'environnement (dev/prod)
- ✅ Meilleure sécurité

---

## 🔒 Gestion des identifiants

### Identifiants actuels (développement local)
```
Username: postgres
Password: postgres
```

### Changer les identifiants

1. **Modifier le fichier** `/home/luffy/Github/Database/.env` :
```env
POSTGRES_USER=votre_username
POSTGRES_PASSWORD=votre_mot_de_passe_securise
POSTGRES_DB=mydb
```

2. **Redémarrer la base de données** :
```bash
cd /home/luffy/Github/Database
make restart
```

3. **Mettre à jour vos fichiers .env de projet** avec les nouveaux identifiants

### Bonnes pratiques
- ❌ Ne jamais commiter `.env` sur Git
- ❌ Ne jamais coder les mots de passe en dur
- ✅ Utiliser des mots de passe forts en production
- ✅ Créer un `.env.example` avec des valeurs fictives

---

## ✅ Vérifier la connexion

Avant de coder, vérifiez que PostgreSQL fonctionne :
```bash
cd /home/luffy/Github/Database
make status
```

Démarrer si nécessaire :
```bash
make start
```

---

## 🆘 Résolution de problèmes

**Erreur "Connection refused"** → PostgreSQL n'est pas démarré : `make start`

**Erreur "Authentication failed"** → Vérifiez les identifiants dans votre `.env`

**Erreur "Cannot find module"** → Installez les dépendances (`pip install` ou `npm install`)
