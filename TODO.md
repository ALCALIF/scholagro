# TODO: Admin Dashboard Product Export and Bulk Import Enhancement

## Completed Tasks
- [x] Add new route `/admin/products/export` in `app/blueprints/admin/routes.py` to export all products to CSV with columns: name, category, price, image_url, stock, slug.
- [x] Add "Export Products" link in the sidebar under E-commerce section in `templates/admin/base.html`.
- [x] Enhance bulk import in `app/tasks.py` to download external image URLs and upload them using media utils, then set the image_url to the uploaded path.

## Followup Steps
- [ ] Test export functionality: Navigate to /admin/products/export and verify CSV download contains accurate product data with categories, prices, and image paths.
- [ ] Test bulk import with images: Upload a CSV with external image URLs and ensure images are downloaded, uploaded to Cloudinary/local storage, and product image_url is set correctly.
- [ ] Verify image paths in export are accurate and match the stored URLs.
- [ ] Ensure no regressions in existing bulk import functionality for products without images.
