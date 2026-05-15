import os
import sys
from dotenv import load_dotenv
load_dotenv()
from app import create_app, db
from app.models.models import User

app = create_app(os.environ.get('FLASK_ENV', 'development'))


def init_db():
    with app.app_context():
        db.create_all()
        
        demo = User.query.filter_by(email='demo@demo.com').first()
        if not demo:
            demo = User(email='demo@demo.com')
            db.session.add(demo)
        demo.set_password('demo')
        db.session.commit()
        print("Demo user ready: demo@demo.com / demo")
        
        print("Database initialized successfully!")


if __name__ == '__main__':
    init_db()
    
    port = 5001
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    
    app.run(host='0.0.0.0', port=port, debug=True)
