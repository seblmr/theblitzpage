from flask import Flask, render_template, request, redirect, session
import stripe
from supabase import create_client, Client
import os
import random

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'blitzpage-secret-2026')
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

supabase: Client = create_client(
    os.environ.get('SUPABASE_URL'),
    os.environ.get('SUPABASE_ANON_KEY')
)

# 12 idées 2026 ultra-dopamine (phone-only, micro-SaaS, creator tools)
HOT_IDEAS = [
    {"name": "SideHustle Scout Bot", "tagline": "Finds profitable phone-only ideas daily", "description": "Telegram bot that scans trends and sends you 3 ready-to-launch side hustles every morning. Zero laptop needed.", "features": "Daily alerts,Copy-paste templates,24h launch plan"},
    {"name": "Content Rocket", "tagline": "Turn 1 YouTube video into 50 posts in 60 seconds", "description": "Instant content repurposer for creators. Paste a link → get X threads, TikToks, LinkedIn posts & newsletter ready.", "features": "Phone-only,Lightning fast,Freemium model"},
    {"name": "BlitzPage", "tagline": "Landing pages in 30 seconds from your phone", "description": "The tool you're using right now. Type 2 sentences → get full HTML + Stripe + X thread.", "features": "24h to first $,Zero laptop,International ready"},
    {"name": "Micro-Influencer Hunter", "tagline": "Finds 50 micro-influencers ready to DM in 1 click", "description": "Scans X & TikTok, finds creators in your niche with <10k followers and high engagement.", "features": "DM templates included,Alerts daily,Phone-only"},
    {"name": "UGC Factory", "tagline": "Generate 30 UGC videos scripts per day", "description": "AI-light script generator for UGC creators. Sell the videos to brands for $50-200 each.", "features": "Zero filming needed,Instant delivery,High demand"},
    {"name": "Notion-to-Gumroad", "tagline": "Turn any Notion page into a $9 product in 10 min", "description": "One-click export + sales page + Stripe checkout.", "features": "Passive income,Phone-only,Tested templates"},
]

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        data = {
            'product_name': request.form.get('product_name'),
            'tagline': request.form.get('tagline'),
            'description': request.form.get('description'),
            'price': request.form.get('price', '16'),
            'cta_text': request.form.get('cta_text', 'Get it now!'),
            'features': [f.strip() for f in request.form.get('features', '').split(',') if f.strip()],
            'email': request.form.get('email', '')
        }
        session['last_landing'] = data
        return render_template('landing.html', **data, paid=False)
    return render_template('index.html')

@app.route('/generate-idea', methods=['POST'])
def generate_idea():
    idea = random.choice(HOT_IDEAS)
    return {
        'product_name': idea['name'],
        'tagline': idea['tagline'],
        'description': idea['description'],
        'features': idea['features']
    }

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        product_name = request.form.get('product_name')
        price_cents = int(float(request.form.get('price', 16)) * 100)
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price_data': {'currency': 'usd', 'product_data': {'name': product_name}, 'unit_amount': price_cents}, 'quantity': 1}],
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
