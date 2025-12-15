from .celery_app import make_celery
from flask import current_app

send_email_task = None
send_email_html_task = None
bulk_import_task = None

def init_celery(app):
    global send_email_task, send_email_html_task
    try:
        celery = make_celery(app)
    except Exception:
        celery = None

    if celery:
        @celery.task(name='app.send_email')
        def _send_email_task(to, subject, body):
            from .utils.email import _send_email_sync
            with app.app_context():
                return _send_email_sync(to, subject, body)
        @celery.task(name='app.send_email_html')
        def _send_email_html_task(to, subject, html):
            from .utils.email import _send_email_html_sync
            with app.app_context():
                return _send_email_html_sync(to, subject, html)
        @celery.task(name='app.bulk_import')
        def _bulk_import_task(file_path):
            # (omitted for brevity) will be executed within Celery worker
            return True
    else:
        # Fallback: define sync functions if celery not available
        def _send_email_task(to, subject, body):
            from .utils.email import _send_email_sync
            with app.app_context():
                return _send_email_sync(to, subject, body)
        def _send_email_html_task(to, subject, html):
            from .utils.email import _send_email_html_sync
            with app.app_context():
                return _send_email_html_sync(to, subject, html)
        def _bulk_import_task(file_path):
            return None
    def _send_email_task(to, subject, body):
        from .utils.email import _send_email_sync
        with app.app_context():
            return _send_email_sync(to, subject, body)

    @celery.task(name='app.send_email_html')
    def _send_email_html_task(to, subject, html):
        from .utils.email import _send_email_html_sync
        with app.app_context():
            return _send_email_html_sync(to, subject, html)

    send_email_task = _send_email_task
    send_email_html_task = _send_email_html_task
    bulk_import_task = _bulk_import_task
    @celery.task(name='app.bulk_import')
    def _bulk_import_task(file_path):
        # Process CSV import in background; import heavy logic from admin
        import csv, io, requests, tempfile
        from .models import Category, Product
        from .utils.media import upload_image
        import pathlib
        try:
            with open(file_path, 'r', encoding='utf-8') as fh:
                reader = csv.DictReader(fh)
                created = 0
                for row in reader:
                    name = row.get('name'); slug = row.get('slug') or (name or '').lower().replace(' ','-')
                    price = row.get('price'); image_url = row.get('image_url'); stock = int(row.get('stock') or 0)
                    cat_name = row.get('category');
                    category = None
                    if cat_name:
                        c = Category.query.filter_by(name=cat_name).first()
                        if not c:
                            c = Category(name=cat_name, slug=(cat_name or '').lower().replace(' ','-'))
                            db.session.add(c)
                            db.session.flush()
                        category = c
                    if name and price:
                        if not Product.query.filter_by(slug=slug).first():
                            # Handle image upload if image_url is provided
                            uploaded_image_url = None
                            if image_url and image_url.startswith(('http://', 'https://')):
                                try:
                                    # Download the image
                                    response = requests.get(image_url, timeout=10)
                                    response.raise_for_status()
                                    # Create a temporary file-like object
                                    from werkzeug.datastructures import FileStorage
                                    import io as io_module
                                    # Save to temp file
                                    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                                        tmp_file.write(response.content)
                                        tmp_file.flush()
                                        # Create FileStorage object
                                        file_storage = FileStorage(stream=io_module.BytesIO(response.content), filename=f"{slug}.jpg", content_type='image/jpeg')
                                        # Upload using media utils
                                        uploaded = upload_image(file_storage, folder="scholagro/products")
                                        if uploaded:
                                            uploaded_image_url = uploaded
                                except Exception:
                                    pass  # If download/upload fails, proceed without image
                            p = Product(name=name, slug=slug, price=price, image_url=uploaded_image_url or image_url, stock=stock, category_id=category.id if category else None)
                            db.session.add(p)
                            created += 1
                db.session.commit()
        except Exception:
            pass
    return celery
