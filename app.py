from flask import Flask, render_template, request
import os

app = Flask(__name__)

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
