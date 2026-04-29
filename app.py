from flask import Flask, render_template, request, redirect, session, abort, jsonify, url_for
from datetime import date, timedelta
from functools import wraps
import stripe
from supabase import create_client, Client
import os
import re
import random
import secrets

app = Flask(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
_secret = os.environ.get('SECRET_KEY')
if not _secret:
    import sys
    if os.environ.get('FLASK_ENV') == 'production':
        print("ERREUR CRITIQUE : SECRET_KEY non définie en production.", file=sys.stderr)
        sys.exit(1)
    _secret = secrets.token_hex(32)
app.secret_key = _secret

stripe.api_key        = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
DOMAIN                = os.environ.get('DOMAIN', 'http://localhost:5000').rstrip('/')

supabase: Client = create_client(
    os.environ.get('SUPABASE_URL'),
    os.environ.get('SUPABASE_ANON_KEY')
)

HOT_IDEAS = [
    {"name": "SideHustle Scout Bot",   "tagline": "Finds profitable phone-only ideas daily",            "description": "Telegram bot that scans trends and sends you 3 ready-to-launch side hustles every morning. Zero laptop needed.",           "features": "Daily alerts,Copy-paste templates,24h launch plan"},
    {"name": "Content Rocket",          "tagline": "Turn 1 YouTube video into 50 posts in 60 seconds",  "description": "Instant content repurposer for creators. Paste a link → get X threads, TikToks, LinkedIn posts & newsletter ready.",     "features": "Phone-only,Lightning fast,Freemium model"},
    {"name": "BlitzPage",               "tagline": "Landing pages in 30 seconds from your phone",       "description": "The tool you're using right now. Type 2 sentences → get full HTML + Stripe + X thread.",                                 "features": "24h to first $,Zero laptop,International ready"},
    {"name": "Micro-Influencer Hunter", "tagline": "Finds 50 micro-influencers ready to DM in 1 click", "description": "Scans X & TikTok, finds creators in your niche with <10k followers and high engagement.",                                "features": "DM templates included,Alerts daily,Phone-only"},
    {"name": "UGC Factory",             "tagline": "Generate 30 UGC video scripts per day",             "description": "AI-light script generator for UGC creators. Sell the videos to brands for $50-200 each.",                               "features": "Zero filming needed,Instant delivery,High demand"},
    {"name": "Notion-to-Gumroad",       "tagline": "Turn any Notion page into a $9 product in 10 min",  "description": "One-click export + sales page + Stripe checkout.",                                                                       "features": "Passive income,Phone-only,Tested templates"},
]
IDEAS_COUNT = len(HOT_IDEAS)

# ── Helpers généraux ──────────────────────────────────────────────────────────

def _validate_price(raw, default=16.0):
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

def _make_slug(product_name: str) -> str:
    base = re.sub(r'[^a-z0-9]+', '-', product_name.lower()).strip('-')[:40]
    for _ in range(5):
        suffix = secrets.token_hex(2)
        slug   = f"{base}-{suffix}"
        exists = supabase.table('landings').select('slug').eq('slug', slug).execute()
        if not exists.data:
            return slug
    return f"{base}-{secrets.token_hex(4)}"

def _landing_url(slug: str) -> str:
    return f"{DOMAIN}/p/{slug}"

# ── Phase 4 : Authentification ────────────────────────────────────────────────

def get_current_user():
    """
    Récupère l'utilisateur connecté depuis la session Flask.
    Valide le token auprès de Supabase Auth à chaque appel.
    Retourne l'objet user Supabase ou None.
    """
    access_token = session.get('access_token')
    if not access_token:
        return None
    try:
        response = supabase.auth.get_user(access_token)
        return response.user
    except Exception:
        # Token expiré ou invalide → nettoyer la session
        session.pop('access_token', None)
        session.pop('user_email', None)
        return None

def login_required(f):
    """Décorateur : redirige vers /login si non connecté."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            session['next'] = request.url   # mémoriser la destination
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated

# ── Routes d'authentification ─────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    GET  : affiche le formulaire d'envoi du magic link
    POST : envoie le magic link via Supabase Auth
    """
    if get_current_user():
        return redirect('/dashboard')

    error   = None
    success = False

    if request.method == 'POST':
        _check_csrf()
        email = request.form.get('email', '').strip().lower()
        if not email:
            error = "Please enter a valid email."
        else:
            try:
                supabase.auth.sign_in_with_otp({
                    'email':   email,
                    'options': {
                        'email_redirect_to': DOMAIN + '/auth/callback',
                        'should_create_user': True,   # crée le compte si inexistant
                    }
                })
                success = True
            except Exception as e:
                error = f"Error sending the link: {str(e)}"

    csrf = _generate_csrf()
    return render_template('login.html', error=error, success=success, csrf_token=csrf)


@app.route('/auth/callback')
def auth_callback():
    """
    Supabase redirige ici après que l'utilisateur a cliqué sur le magic link.
    Le token est dans le fragment d'URL (#) — on le récupère côté client
    puis on le poste en JSON sur /auth/verify.
    """
    return render_template('auth_callback.html')


@app.route('/auth/verify', methods=['POST'])
def auth_verify():
    """
    Reçoit le token depuis le JS de auth_callback.html,
    le vérifie auprès de Supabase et ouvre la session Flask.
    """
    data         = request.get_json(force=True) or {}
    access_token = data.get('access_token', '')
    refresh_token= data.get('refresh_token', '')

    if not access_token:
        return jsonify({'ok': False, 'error': 'Missing token'}), 400

    try:
        response = supabase.auth.get_user(access_token)
        user     = response.user
        if not user:
            raise ValueError("Invalid token")

        # Ouvrir la session Flask
        session['access_token']  = access_token
        session['refresh_token'] = refresh_token
        session['user_email']    = user.email

        next_url = session.pop('next', '/dashboard')
        return jsonify({'ok': True, 'redirect': next_url})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 401


@app.route('/logout')
def logout():
    """Ferme la session Supabase et la session Flask."""
    access_token = session.get('access_token')
    if access_token:
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
    session.clear()
    return redirect('/')

# ── Routes publiques ──────────────────────────────────────────────────────────

@app.route('/', methods=['GET', 'POST'])
def home():
    user = get_current_user()
    if request.method == 'POST':
        _check_csrf()
        price = _validate_price(request.form.get('price', '16'))
        # Si connecté, on prend l'email de la session auth
        email = (user.email if user else None) or request.form.get('email', '').strip().lower()
        data = {
            'product_name': request.form.get('product_name', '').strip(),
            'tagline':      request.form.get('tagline', '').strip(),
            'description':  request.form.get('description', '').strip(),
            'price':        price,
            'cta_text':     request.form.get('cta_text', 'Get it now!').strip(),
            'features':     [f.strip() for f in request.form.get('features', '').split(',') if f.strip()],
            'email':        email,
            'cta_url':      request.form.get('cta_url', '').strip(),
        }
        session['last_landing'] = data
        csrf = _generate_csrf()
        return render_template('landing.html', **data, paid=False, csrf_token=csrf)

    csrf = _generate_csrf()
    return render_template('index.html',
        ideas_count = IDEAS_COUNT,
        csrf_token  = csrf,
        user        = user,
    )


@app.route('/generate-idea', methods=['POST'])
def generate_idea():
    last      = session.get('last_idea_index', -1)
    available = [i for i in range(len(HOT_IDEAS)) if i != last]
    idx       = random.choice(available)
    session['last_idea_index'] = idx
    idea = HOT_IDEAS[idx]
    return jsonify({
        'product_name': idea['name'],
        'tagline':      idea['tagline'],
        'description':  idea['description'],
        'features':     idea['features'],
    })


# ── Phase 1 : landing hébergée ────────────────────────────────────────────────

@app.route('/p/<slug>')
def hosted_landing(slug):
    result = supabase.table('landings') \
        .select('*') \
        .eq('slug', slug) \
        .eq('published', True) \
        .execute()

    if not result.data:
        abort(404)

    landing = result.data[0]

    # Tracking vues global + journalier (fire-and-forget)
    try:
        today = date.today().isoformat()
        supabase.table('landings') \
            .update({'views': (landing.get('views') or 0) + 1}) \
            .eq('slug', slug).execute()
        existing = supabase.table('landing_daily_views') \
            .select('id, views').eq('slug', slug).eq('day', today).execute()
        if existing.data:
            supabase.table('landing_daily_views') \
                .update({'views': existing.data[0]['views'] + 1}) \
                .eq('id', existing.data[0]['id']).execute()
        else:
            supabase.table('landing_daily_views') \
                .insert({'slug': slug, 'day': today, 'views': 1}).execute()
    except Exception:
        pass

    features = landing.get('features') or []
    if isinstance(features, str):
        features = [f.strip() for f in features.split(',') if f.strip()]

    return render_template('hosted_landing.html',
        product_name = landing['product_name'],
        tagline      = landing.get('tagline', ''),
        description  = landing.get('description', ''),
        price        = landing.get('price', ''),
        features     = features,
        cta_text     = landing.get('cta_text', 'Get it now!'),
        cta_url      = landing.get('cta_url', ''),
        slug         = slug,
    )


# ── Paiement BlitzPage ────────────────────────────────────────────────────────

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    _check_csrf()
    product_name = request.form.get('product_name', 'Product')
    price        = _validate_price(request.form.get('price', '16'))
    price_cents  = int(price * 100)
    try:
        cs = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency':     'usd',
                    'product_data': {'name': f"BlitzPage — {product_name}"},
                    'unit_amount':  price_cents,
                },
                'quantity': 1,
            }],
            mode='payment',
            metadata={'email': session.get('last_landing', {}).get('email', '')},
            success_url = DOMAIN + '/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url  = DOMAIN + '/cancel',
        )
        return redirect(cs.url, code=303)
    except Exception as e:
        return str(e), 500


@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload    = request.get_data()
    sig_header = request.headers.get('Stripe-Signature', '')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        abort(400)
    if event['type'] == 'checkout.session.completed':
        cs    = event['data']['object']
        email = cs.get('metadata', {}).get('email', '')
        if email:
            supabase.table('landings') \
                .update({'paid': True}) \
                .eq('email', email).eq('paid', False).execute()
    return '', 200


@app.route('/success')
def success():
    session_id = request.args.get('session_id', '')
    data       = session.get('last_landing', {})

    if session_id and data:
        try:
            cs = stripe.checkout.Session.retrieve(session_id)
            if cs.payment_status == 'paid':
                slug = _make_slug(data.get('product_name', 'product'))
                supabase.table('landings').upsert({
                    'product_name': data.get('product_name'),
                    'tagline':      data.get('tagline'),
                    'description':  data.get('description'),
                    'price':        str(data.get('price')),
                    'features':     data.get('features'),
                    'cta_text':     data.get('cta_text'),
                    'cta_url':      data.get('cta_url', ''),
                    'email':        data.get('email'),
                    'paid':         True,
                    'published':    True,
                    'slug':         slug,
                    'views':        0,
                }, on_conflict='email,product_name').execute()
                data['paid']        = True
                data['slug']        = slug
                data['landing_url'] = _landing_url(slug)
                session['last_landing'] = data
                return render_template('landing.html', **data, csrf_token=_generate_csrf())
        except Exception:
            pass

    return render_template('success.html')


# ── Phase 2 : fil public des lancements ───────────────────────────────────────

TRENDING_THRESHOLD = 50

@app.route('/launches')
def launches():
    sort     = request.args.get('sort', 'latest')
    page     = max(1, int(request.args.get('page', 1)))
    per_page = 12
    offset   = (page - 1) * per_page

    query = supabase.table('landings') \
        .select('product_name, tagline, description, price, slug, views, created_at, features') \
        .eq('published', True)

    query = query.order('views', desc=True) if sort == 'trending' \
            else query.order('created_at', desc=True)

    result   = query.range(offset, offset + per_page - 1).execute()
    landings = result.data or []

    for l in landings:
        l['url']      = _landing_url(l['slug'])
        l['trending'] = (l.get('views') or 0) >= TRENDING_THRESHOLD

    count_result = supabase.table('landings') \
        .select('id', count='exact').eq('published', True).execute()
    total    = count_result.count or 0
    has_next = (offset + per_page) < total
    has_prev = page > 1

    return render_template('launches.html',
        landings = landings, sort = sort, page = page,
        has_next = has_next, has_prev = has_prev, total = total,
    )


# ── Phase 3 : Analytics ───────────────────────────────────────────────────────

@app.route('/api/analytics/<slug>')
@login_required
def analytics(slug):
    user = get_current_user()
    # Vérifier que la landing appartient à l'utilisateur connecté
    check = supabase.table('landings') \
        .select('slug').eq('slug', slug).eq('email', user.email).execute()
    if not check.data:
        abort(403)

    today  = date.today()
    since  = (today - timedelta(days=29)).isoformat()
    result = supabase.table('landing_daily_views') \
        .select('day, views').eq('slug', slug) \
        .gte('day', since).order('day').execute()

    rows      = {r['day']: r['views'] for r in (result.data or [])}
    full_data = [
        {'day': (today - timedelta(days=29 - i)).isoformat(),
         'views': rows.get((today - timedelta(days=29 - i)).isoformat(), 0)}
        for i in range(30)
    ]
    return jsonify({'slug': slug, 'data': full_data})


# ── Phase 4 : Dashboard sécurisé ─────────────────────────────────────────────

@app.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    user  = get_current_user()
    email = user.email

    result = supabase.table('landings') \
        .select('product_name, tagline, slug, views, published, created_at, price') \
        .eq('email', email).eq('paid', True) \
        .order('created_at', desc=True).execute()
    landings = result.data or []

    for l in landings:
        l['url'] = _landing_url(l['slug']) if l.get('slug') else None

    return render_template('dashboard.html',
        email    = email,
        landings = landings,
        domain   = DOMAIN,
        user     = user,
    )


@app.route('/my-landings')
def my_landings():
    return redirect('/dashboard', code=301)


@app.route('/cancel')
def cancel():
    return render_template('cancel.html')


if __name__ == '__main__':
    port  = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug)
