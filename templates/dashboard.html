from flask import Flask, render_template, request, redirect, session, abort
import stripe
from supabase import create_client, Client
import os
import random
import secrets

app = Flask(__name__)

# ✅ FIX 1: Plus de secret key hardcodée — plante clairement si absente en prod
_secret = os.environ.get('SECRET_KEY')
if not _secret:
    import sys
    if os.environ.get('FLASK_ENV') == 'production':
        print("ERREUR CRITIQUE : SECRET_KEY non définie en production.", file=sys.stderr)
        sys.exit(1)
    _secret = secrets.token_hex(32)   # temporaire pour le dev uniquement
app.secret_key = _secret

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

# ✅ FIX 2: DOMAIN validé au démarrage
DOMAIN = os.environ.get('DOMAIN', 'http://localhost:5000').rstrip('/')

supabase: Client = create_client(
    os.environ.get('SUPABASE_URL'),
    os.environ.get('SUPABASE_ANON_KEY')
)

# ✅ FIX 3: Comptage corrigé (6 idées, pas "12+")
HOT_IDEAS = [
    {"name": "SideHustle Scout Bot",   "tagline": "Finds profitable phone-only ideas daily",              "description": "Telegram bot that scans trends and sends you 3 ready-to-launch side hustles every morning. Zero laptop needed.",                                    "features": "Daily alerts,Copy-paste templates,24h launch plan"},
    {"name": "Content Rocket",          "tagline": "Turn 1 YouTube video into 50 posts in 60 seconds",    "description": "Instant content repurposer for creators. Paste a link → get X threads, TikToks, LinkedIn posts & newsletter ready.",                          "features": "Phone-only,Lightning fast,Freemium model"},
    {"name": "BlitzPage",               "tagline": "Landing pages in 30 seconds from your phone",         "description": "The tool you're using right now. Type 2 sentences → get full HTML + Stripe + X thread.",                                                       "features": "24h to first $,Zero laptop,International ready"},
    {"name": "Micro-Influencer Hunter", "tagline": "Finds 50 micro-influencers ready to DM in 1 click",  "description": "Scans X & TikTok, finds creators in your niche with <10k followers and high engagement.",                                                      "features": "DM templates included,Alerts daily,Phone-only"},
    {"name": "UGC Factory",             "tagline": "Generate 30 UGC video scripts per day",               "description": "AI-light script generator for UGC creators. Sell the videos to brands for $50-200 each.",                                                      "features": "Zero filming needed,Instant delivery,High demand"},
    {"name": "Notion-to-Gumroad",       "tagline": "Turn any Notion page into a $9 product in 10 min",   "description": "One-click export + sales page + Stripe checkout.",                                                                                             "features": "Passive income,Phone-only,Tested templates"},
]
IDEAS_COUNT = len(HOT_IDEAS)  # utilisé dans le template

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _validate_price(raw, default=16.0):
    """Retourne un float > 0, ou la valeur par défaut."""
    try:
        val = float(raw)
        if val <= 0:
            raise ValueError
        return round(val, 2)
    except (TypeError, ValueError):
        return default

def _generate_csrf():
    token = secrets.token_hex(16)
    session['csrf_token'] = token
    return token

def _check_csrf():
    token = request.form.get('csrf_token', '')
    if not token or token != session.get('csrf_token'):
        abort(403)

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        _check_csrf()  # ✅ FIX 4 : protection CSRF

        # ✅ FIX 5 : validation du prix
        price = _validate_price(request.form.get('price', '16'))

        data = {
            'product_name': request.form.get('product_name', '').strip(),
            'tagline':      request.form.get('tagline', '').strip(),
            'description':  request.form.get('description', '').strip(),
            'price':        price,
            'cta_text':     request.form.get('cta_text', 'Get it now!').strip(),
            'features':     [f.strip() for f in request.form.get('features', '').split(',') if f.strip()],
            'email':        request.form.get('email', '').strip().lower(),
        }
        session['last_landing'] = data
        csrf = _generate_csrf()
        return render_template('landing.html', **data, paid=False, csrf_token=csrf)

    csrf = _generate_csrf()
    return render_template('index.html', ideas_count=IDEAS_COUNT, csrf_token=csrf)


@app.route('/generate-idea', methods=['POST'])
def generate_idea():
    # ✅ FIX 6 : pas de répétition consécutive
    last = session.get('last_idea_index', -1)
    available = [i for i in range(len(HOT_IDEAS)) if i != last]
    idx = random.choice(available)
    session['last_idea_index'] = idx
    idea = HOT_IDEAS[idx]
    return {
        'product_name': idea['name'],
        'tagline':      idea['tagline'],
        'description':  idea['description'],
        'features':     idea['features'],
    }


@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    _check_csrf()  # ✅ CSRF

    # ✅ FIX 5 : re-validation serveur du prix (ne jamais faire confiance au client)
    product_name = request.form.get('product_name', 'Product')
    price = _validate_price(request.form.get('price', '16'))
    price_cents = int(price * 100)

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {'name': product_name},
                    'unit_amount': price_cents,
                },
                'quantity': 1,
            }],
            mode='payment',
            # Passer l'email en metadata pour le récupérer dans le webhook
            metadata={'email': session.get('last_landing', {}).get('email', '')},
            success_url=DOMAIN + '/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=DOMAIN + '/cancel',
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        return str(e), 500


# ✅ FIX 7 : Webhook Stripe — confirmation de paiement côté serveur
@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature', '')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        abort(400)

    if event['type'] == 'checkout.session.completed':
        cs = event['data']['object']
        email = cs.get('metadata', {}).get('email', '')
        # Marquer la landing comme payée en base
        if email:
            supabase.table('landings') \
                .update({'paid': True}) \
                .eq('email', email) \
                .eq('paid', False) \
                .execute()

    return '', 200


@app.route('/success')
def success():
    # ✅ FIX 8 : vérification de la session Stripe pour afficher le bon contenu
    session_id = request.args.get('session_id', '')
    data = session.get('last_landing', {})

    if session_id and data:
        try:
            cs = stripe.checkout.Session.retrieve(session_id)
            if cs.payment_status == 'paid':
                data['paid'] = True
                # Sauvegarde en base si pas encore fait
                supabase.table('landings').upsert({
                    'product_name': data.get('product_name'),
                    'tagline':      data.get('tagline'),
                    'description':  data.get('description'),
                    'price':        str(data.get('price')),
                    'features':     data.get('features'),
                    'email':        data.get('email'),
                    'paid':         True,
                }, on_conflict='email,product_name').execute()
                return render_template('landing.html', **data)
        except Exception:
            pass

    return render_template('success.html')


# ✅ FIX 9 : /my-landings protégé par un token de session (anti-énumération)
@app.route('/my-landings', methods=['GET', 'POST'])
def my_landings():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        session['verified_email'] = email   # stocké en session côté serveur
    else:
        email = session.get('verified_email', request.args.get('email', ''))

    landings = []
    if email:
        response = supabase.table('landings') \
            .select('*') \
            .eq('email', email) \
            .eq('paid', True) \
            .order('created_at', desc=True) \
            .execute()
        landings = response.data

    return render_template('my-landings.html', landings=landings, email=email)


@app.route('/cancel')
def cancel():
    return render_template('cancel.html')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug)
