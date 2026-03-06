from src.main import create_app, start_scheduler
from src.utils.logger import setup_logger

setup_logger()
app = create_app()
scheduler = start_scheduler(app)

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        scheduler.shutdown()
