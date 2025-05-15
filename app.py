import os
from flask import Flask, request, render_template_string
import pandas as pd
import openai

# OpenAI API key instellen:
# export OPENAI_API_KEY="je_api_key"
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

UPLOAD_FORM = '''
<!doctype html>
<title>Nakijksysteem Demo</title>
<h1>Upload bestanden</h1>
<form method=post enctype=multipart/form-data>
  Leerling-antwoorden CSV: <input type=file name=student_file><br><br>
  Model-antwoorden CSV:  <input type=file name=model_file><br><br>
  <input type=submit value=Vergelijk>
</form>
'''

RESULT_TEMPLATE = '''
<!doctype html>
<title>Resultaten</title>
<h1>Resultaten</h1>

<h2>Totale scores</h2>
<table border=1 cellpadding=5>
  <tr><th>student_id</th><th>totaal</th><th>max</th><th>%</th></tr>
  {% for t in totals %}
  <tr>
    <td>{{ t.student_id }}</td>
    <td>{{ "%.2f"|format(t.total_score) }}</td>
    <td>{{ t.max_score }}</td>
    <td>{{ "%.1f"|format(t.percentage * 100) }}%</td>
  </tr>
  {% endfor %}
</table>

<hr>

<h2>Details per vraag</h2>
<table border=1 cellpadding=5>
<tr><th>student_id</th><th>vraag</th><th>score</th><th>feedback</th></tr>
{% for r in results %}
<tr>
  <td>{{ r.student_id }}</td>
  <td>{{ r.question }}</td>
  <td>{{ "%.2f"|format(r.score) }}</td>
  <td>{{ r.feedback }}</td>
</tr>
{% endfor %}
</table>
'''

@app.route('/', methods=['GET','POST'])
def index():
    try:
        if request.method == 'POST':
            # bestanden inlezen
            df_students = pd.read_csv(request.files['student_file'])
            df_model    = pd.read_csv(request.files['model_file'])
            questions   = list(df_model['question'])
            model_dict  = dict(zip(questions, df_model['modelanswer']))

            results = []
            # per student & vraag AI-call
            for _, row in df_students.iterrows():
                sid = row['student_id']
                for q in questions:
                    student_ans = str(row.get(q, ''))
                    model_ans   = model_dict[q]
                    prompt = (
                        f"Beoordeel dit antwoord:\n"
                        f"Vraag: {q}\n"
                        f"Modelantwoord: {model_ans}\n"
                        f"Leerlingantwoord: {student_ans}\n"
                        "Geef JSON met 'score'(0-1) en 'feedback'."
                    )
                    # **Nieuw: nieuwe API-call**
                    resp = openai.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role":"user", "content": prompt}]
                    )
                    content = resp.choices[0].message.content
                    try:
                        obj = __import__('json').loads(content)
                        score    = float(obj.get('score', 0))
                        feedback = obj.get('feedback','').strip()
                    except:
                        score    = 0.0
                        feedback = content.strip()

                    results.append({
                        'student_id': sid,
                        'question':    q,
                        'score':       score,
                        'feedback':    feedback
                    })

            # totaal per student
            df_res = pd.DataFrame(results)
            totals = []
            max_score = len(questions)
            for sid, grp in df_res.groupby('student_id'):
                total = grp['score'].sum()
                perc  = total / max_score if max_score else 0
                totals.append({
                    'student_id': sid,
                    'total_score': total,
                    'max_score':   max_score,
                    'percentage':  perc
                })

            return render_template_string(RESULT_TEMPLATE,
                                          results=results,
                                          totals=totals)
        return UPLOAD_FORM

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"<pre>Fout in de server:\n{e}</pre>", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
