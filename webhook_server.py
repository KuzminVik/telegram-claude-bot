#!/usr/bin/env python3
"""
GitHub Webhook Server для автоматического code review
Принимает webhook события от GitHub при создании/обновлении PR
"""

import os
import hmac
import hashlib
import json
import logging
from flask import Flask, request, jsonify
from handlers.pr_review import process_pr_review

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# GitHub webhook secret для валидации
WEBHOOK_SECRET = os.getenv('GITHUB_WEBHOOK_SECRET', '')

def verify_signature(payload_body, signature_header):
    """Проверка подписи webhook от GitHub"""
    if not WEBHOOK_SECRET:
        logger.warning("GITHUB_WEBHOOK_SECRET не установлен, пропускаю проверку")
        return True
    
    hash_object = hmac.new(
        WEBHOOK_SECRET.encode('utf-8'),
        msg=payload_body,
        digestmod=hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()
    
    if not hmac.compare_digest(expected_signature, signature_header):
        logger.error("Неверная подпись webhook")
        return False
    return True

@app.route('/webhook/github', methods=['POST'])
def github_webhook():
    """Endpoint для получения webhook от GitHub"""
    try:
        # Валидация подписи
        signature = request.headers.get('X-Hub-Signature-256', '')
        if not verify_signature(request.data, signature):
            return jsonify({'error': 'Invalid signature'}), 401
        
        # Получение типа события
        event_type = request.headers.get('X-GitHub-Event')
        payload = request.json
        
        logger.info(f"Получен webhook: {event_type}")
        
        # Обработка Pull Request событий
        if event_type == 'pull_request':
            action = payload.get('action')
            
            # Реагируем на создание и обновление PR
            if action in ['opened', 'synchronize', 'reopened']:
                pr_data = payload.get('pull_request', {})
                repo_data = payload.get('repository', {})
                
                pr_number = pr_data.get('number')
                pr_title = pr_data.get('title')
                pr_url = pr_data.get('html_url')
                repo_full_name = repo_data.get('full_name')
                
                logger.info(
                    f"PR #{pr_number} {action}: {pr_title} в {repo_full_name}"
                )
                
                # Асинхронная обработка ревью
                try:
                    process_pr_review(payload)
                    return jsonify({
                        'status': 'success',
                        'message': f'Review started for PR #{pr_number}'
                    }), 200
                except Exception as e:
                    logger.error(f"Ошибка при обработке PR: {e}")
                    return jsonify({
                        'status': 'error',
                        'message': str(e)
                    }), 500
            else:
                logger.info(f"Игнорируем action: {action}")
                return jsonify({
                    'status': 'ignored',
                    'message': f'Action {action} not processed'
                }), 200
        
        # Ping event (для проверки webhook)
        elif event_type == 'ping':
            logger.info("Ping received from GitHub")
            return jsonify({
                'status': 'success',
                'message': 'Pong!'
            }), 200
        
        else:
            logger.info(f"Неподдерживаемый тип события: {event_type}")
            return jsonify({
                'status': 'ignored',
                'message': f'Event type {event_type} not supported'
            }), 200
            
    except Exception as e:
        logger.error(f"Ошибка при обработке webhook: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'github-webhook-server'
    }), 200

if __name__ == '__main__':
    port = int(os.getenv('WEBHOOK_PORT', 8080))
    logger.info(f"Запуск webhook сервера на порту {port}")
    
    # В production используйте gunicorn/uwsgi
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False
    )
