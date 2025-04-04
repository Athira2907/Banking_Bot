# app.py
from flask import Flask, request, jsonify, render_template, session
import os
import sqlite3
import datetime
import json
import requests
from functools import wraps
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management

# Database setup
def init_db():
    conn = sqlite3.connect('banking.db')
    cursor = conn.cursor()
    
    # Create tables if they don't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        balance REAL DEFAULT 1000.00
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        transaction_type TEXT NOT NULL,
        amount REAL NOT NULL,
        recipient TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    # Insert sample user if not exists
    cursor.execute("SELECT * FROM users WHERE username = 'demo_user'")
    if not cursor.fetchone():
        cursor.execute('''
        INSERT INTO users (username, password, full_name, email, balance)
        VALUES ('demo_user', 'password123', 'Demo User', 'demo@example.com', 5000.00)
        ''')
    
    conn.commit()
    conn.close()

# Initialize database at startup
init_db()

# Simple OpenAI integration
def get_ai_response(prompt, api_key=None):
    """Get response from OpenAI API or use mock response if no API key"""
    if api_key:
        try:
            # OpenAI API integration
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            }
            data = {
                'model': 'gpt-3.5-turbo',
                'messages': [{'role': 'system', 'content': 'You are a helpful banking assistant.'}, 
                             {'role': 'user', 'content': prompt}],
                'temperature': 0.7,
                'max_tokens': 150
            }
            response = requests.post('https://api.openai.com/v1/chat/completions', 
                                    headers=headers, 
                                    data=json.dumps(data),
                                    timeout=10)
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            else:
                logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
                return get_mock_response(prompt)
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {str(e)}")
            return get_mock_response(prompt)
    else:
        return get_mock_response(prompt)

def get_mock_response(prompt):
    """Generate a mock response for when OpenAI API is not available"""
    prompt_lower = prompt.lower()
    
    if "balance" in prompt_lower:
        return "I can help you check your account balance. Based on your account information, I can see your current balance in the system."
    
    elif "transfer" in prompt_lower:
        return "I understand you want to make a transfer. Please specify the amount and recipient, for example: 'Transfer $50 to John'."
    
    elif "transaction" in prompt_lower or "history" in prompt_lower:
        return "I can help you review your recent transactions. Your transaction history shows your recent activity including deposits, withdrawals, and transfers."
    
    elif "help" in prompt_lower:
        return "I can help with checking your balance, making transfers, and reviewing your transaction history. What would you like to do today?"
    
    else:
        return "I'm your banking assistant. I can help with checking your balance, making transfers, and reviewing your transaction history. How can I assist you today?"

# Helper functions for banking operations
def get_user_by_username(username):
    conn = sqlite3.connect('banking.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {
            "id": user[0],
            "username": user[1],
            "password": user[2],
            "full_name": user[3],
            "email": user[4],
            "balance": user[5]
        }
    return None

def get_recent_transactions(user_id, limit=5):
    conn = sqlite3.connect('banking.db')
    cursor = conn.cursor()
    cursor.execute("""
    SELECT transaction_type, amount, recipient, timestamp 
    FROM transactions 
    WHERE user_id = ? 
    ORDER BY timestamp DESC LIMIT ?
    """, (user_id, limit))
    
    transactions = cursor.fetchall()
    conn.close()
    
    transaction_list = []
    for t in transactions:
        transaction_list.append({
            "type": t[0],
            "amount": t[1],
            "recipient": t[2],
            "timestamp": t[3]
        })
    
    return transaction_list

def format_transactions(transactions):
    if not transactions:
        return "No recent transactions."
    
    formatted = []
    for t in transactions:
        if t["type"] == "deposit":
            formatted.append(f"DEPOSIT: +${t['amount']:.2f} on {t['timestamp']}")
        elif t["type"] == "withdrawal":
            formatted.append(f"WITHDRAWAL: -${t['amount']:.2f} on {t['timestamp']}")
        elif t["type"] == "transfer":
            formatted.append(f"TRANSFER: -${t['amount']:.2f} to {t['recipient']} on {t['timestamp']}")
    
    return "\n".join(formatted)

def update_balance(user_id, amount, transaction_type, recipient=None):
    conn = sqlite3.connect('banking.db')
    cursor = conn.cursor()
    
    # Update user balance
    if transaction_type in ['withdrawal', 'transfer']:
        cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (amount, user_id))
    else:  # deposit
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user_id))
    
    # Record transaction
    cursor.execute("""
    INSERT INTO transactions (user_id, transaction_type, amount, recipient, timestamp)
    VALUES (?, ?, ?, ?, ?)
    """, (user_id, transaction_type, amount, recipient, datetime.datetime.now()))
    
    conn.commit()
    conn.close()

# Flask routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    user = get_user_by_username(username)
    
    if user and user['password'] == password:
        session['user_id'] = user['id']
        session['username'] = user['username']
        return jsonify({
            "success": True,
            "user": {
                "username": user['username'],
                "full_name": user['full_name'],
                "balance": user['balance']
            }
        })
    else:
        return jsonify({"success": False, "message": "Invalid credentials"}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    return jsonify({"success": True})

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    message = data.get('message')
    username = data.get('username')
    
    user = get_user_by_username(username)
    
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404
    
    # Process banking commands directly
    if "transfer" in message.lower() and "$" in message:
        # Simple parsing for transfer commands
        try:
            amount = float(''.join(filter(lambda x: x.isdigit() or x == '.', 
                        message.split("$")[1].split(" ")[0])))
            recipient = None
            
            if "to" in message.lower():
                recipient = message.lower().split("to")[1].strip().split(" ")[0]
            
            if amount <= 0:
                return jsonify({"success": False, "message": "Invalid amount"})
            
            if amount > user['balance']:
                return jsonify({"success": False, "message": "Insufficient funds"})
                
            update_balance(user['id'], amount, "transfer", recipient)
            
            # Refresh user data
            user = get_user_by_username(username)
            response = f"Successfully transferred ${amount:.2f}"
            if recipient:
                response += f" to {recipient}"
            response += f". Your new balance is ${user['balance']:.2f}"
            
            return jsonify({"success": True, "message": response})
        except Exception as e:
            logger.error(f"Transfer error: {str(e)}")
            return jsonify({"success": False, "message": "Unable to process transfer. Please try again."})
    
    # Process balance inquiry
    if "balance" in message.lower():
        response = f"Your current balance is ${user['balance']:.2f}."
        return jsonify({"success": True, "message": response})
    
    # Process transaction history
    if "transaction" in message.lower() or "history" in message.lower():
        transactions = get_recent_transactions(user['id'])
        formatted = format_transactions(transactions)
        response = f"Here are your recent transactions:\n\n{formatted}"
        return jsonify({"success": True, "message": response})
    
    # Get AI response for other queries
    transactions = get_recent_transactions(user['id'])
    formatted_transactions = format_transactions(transactions)
    
    prompt = f"""
    User: {message}
    
    User Info:
    Name: {user['full_name']}
    Balance: ${user['balance']:.2f}
    
    Recent Transactions:
    {formatted_transactions}
    
    Please provide a helpful response as a banking assistant.
    """
    
    # Get API key from environment or use mock response
    api_key = os.environ.get('OPENAI_API_KEY', None)
    response = get_ai_response(prompt, api_key)
    
    return jsonify({"success": True, "message": response})

@app.route('/api/transactions', methods=['GET'])
def get_transactions_api():
    username = request.args.get('username')
    user = get_user_by_username(username)
    
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404
    
    transactions = get_recent_transactions(user['id'], limit=10)
    return jsonify({"success": True, "transactions": transactions})

if __name__ == '__main__':
    app.run(debug=True)
