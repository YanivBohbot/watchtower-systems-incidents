from app.api import create_app
from app.config import settings

app = create_app(settings())
