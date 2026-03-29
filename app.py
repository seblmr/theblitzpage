from flask import Flask, render_template, request, redirect
import stripe
import os

app = Flask(__name__)

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        data = {
            'product_name': request.form.get('product_name', 'My Awesome Product'),
            'tagline': request.form.get('tagline', 'The tool that changes the game'),
            'description': request.form.get('description', 'Full description of your product here.'),
            'price': request.form.get('price', '19'),
            'cta_text': request.form.get('cta_text', 'Get it now!'),
            'audience': request.form.get('audience', 'Indie hackers & creators'),
            'features': [f.strip() for f in request.form.get('features', 'Lightning fast,Phone-only,Zero budget').split(',') if f.strip()]
        }
        while len(data['features']) < 3:
            data['features'].append(['Lightning fast', 'Phone-only', 'Zero budget'][len(data['features'])])
        return render_template('landing.html', **data)
    return render_template('index.html')

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        product_name = request.form.get('product_name')
        price_cents = int(float(request.form.get('price', 19)) * 100)
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {'name': product_name},
                    'unit_amount': price_cents,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=os.environ.get('DOMAIN') + '/success',
            cancel_url=os.environ.get('DOMAIN') + '/cancel',
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        return str(e), 500

@app.route('/success')
def success():
    return render_template('success.html')

@app.route('/cancel')
def cancel():
    return render_template('cancel.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
