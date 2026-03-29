from flask import Flask, render_template, request, redirect, session
import stripe
from supabase import create_client, Client
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'blitzpage-secret-2026')
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

supabase: Client = create_client(
    os.environ.get('SUPABASE_URL'),
    os.environ.get('SUPABASE_ANON_KEY')
)

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        data = {
            'product_name': request.form.get('product_name', 'Mon Awesome Produit'),
            'tagline': request.form.get('tagline', 'Le tool qui change la game'),
            'description': request.form.get('description', 'Description complète de ton produit ici.'),
            'price': request.form.get('price', '19'),
            'cta_text': request.form.get('cta_text', 'Je veux ça maintenant !'),
            'features': [f.strip() for f in request.form.get('features', 'Ultra rapide,Phone-only,Zéro euro').split(',') if f.strip()],
            'email': request.form.get('email', '')
        }
        while len(data['features']) < 3:
            data['features'].append(['Ultra rapide', 'Phone-only', 'Zéro euro'][len(data['features'])])
        
        session['last_landing'] = data
        return render_template('landing.html', **data, paid=False)
    return render_template('index.html')

# (le reste du code reste identique à V7 : create-checkout-session, success, my-landings, cancel)

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
    data = session.get('last_landing', {})
    if data and data.get('email'):
        data['paid'] = True
        supabase.table('landings').insert({
            'product_name': data['product_name'],
            'tagline': data['tagline'],
            'description': data['description'],
            'price': data['price'],
            'features': data['features'],
            'email': data['email']
        }).execute()
        return render_template('landing.html', **data)
    return render_template('success.html')

@app.route('/my-landings', methods=['GET', 'POST'])
def my_landings():
    if request.method == 'POST':
        email = request.form.get('email')
    else:
        email = request.args.get('email', '')
    if email:
        response = supabase.table('landings').select('*').eq('email', email).order('created_at', desc=True).execute()
        landings = response.data
    else:
        landings = []
    return render_template('my-landings.html', landings=landings, email=email)

@app.route('/cancel')
def cancel():
    return render_template('cancel.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
