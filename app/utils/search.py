import os
try:
    from algoliasearch.search_client import SearchClient
except Exception:
    SearchClient = None

def get_algolia_client():
    if not SearchClient:
        return None
    id = os.getenv('ALGOLIA_APP_ID')
    key = os.getenv('ALGOLIA_ADMIN_KEY')
    if not id or not key:
        return None
    return SearchClient.create(id, key)

def index_product(product):
    client = get_algolia_client()
    if not client:
        return False
    index = client.init_index('scholagro_products')
    try:
        index.save_object({
            'objectID': str(product.id),
            'name': product.name,
            'slug': product.slug,
            'price': float(product.price) if product.price else 0,
            'category_id': product.category_id,
            'is_active': bool(product.is_active)
        })
        return True
    except Exception:
        return False
