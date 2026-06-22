import re

with open('server.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace download_result_csv with download_result_pdf
csv_result_func = '''    @app.route("/download/result/<int:attempt_id>/csv")
    @login_required
    def download_result_csv(attempt_id):
        attempt = db.session.get(QuizAttempt, attempt_id)
        if not attempt:
            flash("Attempt not found.", "error")
            return redirect(url_for("dashboard"))

        if attempt.user_id != session["user_id"] and session.get("role") != "admin":
            flash("You cannot download that result.", "error")
            return redirect(url_for("dashboard"))

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Quiz Result Report"])
        writer.writerow([])
        writer.writerow(["Student Name", session.get("username")])
        writer.writerow(["Subject", attempt.subject])
        writer.writerow(["Date Taken", attempt.date_taken])
        writer.writerow(["Total Questions", attempt.total_questions])
        writer.writerow(["Correct Answers", attempt.correct_answers])
        writer.writerow(["Percentage", f"{attempt.percentage}%"])
        writer.writerow(["Time Taken", f"{attempt.time_taken // 60}m {attempt.time_taken % 60}s"])
        writer.writerow([])
        writer.writerow(["Question", "Your Answer", "Correct Answer", "Result"])
        
        for answer in attempt.answers:
            result = "Correct" if answer.is_correct else "Incorrect"
            writer.writerow([
                answer.text[:50],
                answer.selected_option or "Not Answered",
                answer.correct_option,
                result
            ])

        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename=quiz_result_{attempt_id}.csv"}
        )'''

pdf_result_func = '''    @app.route("/download/result/<int:attempt_id>/pdf")
    @login_required
    def download_result_pdf(attempt_id):
        attempt = db.session.get(QuizAttempt, attempt_id)
        if not attempt:
            flash("Attempt not found.", "error")
            return redirect(url_for("dashboard"))

        if attempt.user_id != session["user_id"] and session.get("role") != "admin":
            flash("You cannot download that result.", "error")
            return redirect(url_for("dashboard"))

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="Quiz Result Report", ln=True, align="C")
        pdf.ln(5)
        pdf.cell(200, 10, txt=f"Student Name: {session.get('username')}", ln=True)
        pdf.cell(200, 10, txt=f"Subject: {attempt.subject}", ln=True)
        pdf.cell(200, 10, txt=f"Date Taken: {attempt.date_taken}", ln=True)
        pdf.cell(200, 10, txt=f"Total Questions: {attempt.total_questions}", ln=True)
        pdf.cell(200, 10, txt=f"Correct Answers: {attempt.correct_answers}", ln=True)
        pdf.cell(200, 10, txt=f"Percentage: {attempt.percentage}%", ln=True)
        pdf.cell(200, 10, txt=f"Time Taken: {attempt.time_taken // 60}m {attempt.time_taken % 60}s", ln=True)
        pdf.ln(5)
        
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(100, 10, "Question", border=1)
        pdf.cell(30, 10, "Your Answer", border=1)
        pdf.cell(30, 10, "Correct Answer", border=1)
        pdf.cell(30, 10, "Result", border=1)
        pdf.ln(10)
        
        pdf.set_font("Arial", size=10)
        for answer in attempt.answers:
            result = "Correct" if answer.is_correct else "Incorrect"
            pdf.cell(100, 10, str(answer.text)[:45].encode('latin-1', 'replace').decode('latin-1'), border=1)
            pdf.cell(30, 10, str(answer.selected_option or "None").encode('latin-1', 'replace').decode('latin-1'), border=1)
            pdf.cell(30, 10, str(answer.correct_option).encode('latin-1', 'replace').decode('latin-1'), border=1)
            pdf.cell(30, 10, result.encode('latin-1', 'replace').decode('latin-1'), border=1)
            pdf.ln(10)
            
        return Response(
            bytes(pdf.output(dest='S'), 'latin-1'),
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment;filename=quiz_result_{attempt_id}.pdf"}
        )'''

# Replace download_questions_csv with pdf equivalent
csv_questions_func = '''    @app.route("/download/questions/<subject>/csv")
    @login_required
    @admin_required
    def download_questions_csv(subject):
        questions = Question.query.filter_by(subject=subject).all()
        if not questions:
            flash("No questions found for this subject.", "error")
            return redirect(url_for("admin"))

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Subject", "Difficulty", "Question", "Option A", "Option B", "Option C", "Option D", "Correct", "Explanation"])
        
        for q in questions:
            writer.writerow([
                q.subject,
                q.difficulty,
                q.text,
                q.option_a,
                q.option_b,
                q.option_c,
                q.option_d,
                q.correct_option,
                q.explanation or ""
            ])

        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={subject.replace(' ', '_')}_questions.csv"}
        )'''

pdf_questions_func = '''    @app.route("/download/questions/<subject>/pdf")
    @login_required
    @admin_required
    def download_questions_pdf(subject):
        questions = Question.query.filter_by(subject=subject).all()
        if not questions:
            flash("No questions found for this subject.", "error")
            return redirect(url_for("admin"))

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=f"{subject} Questions Bank", ln=True, align="C")
        pdf.ln(5)
        
        pdf.set_font("Arial", size=10)
        for i, q in enumerate(questions, 1):
            pdf.multi_cell(0, 8, txt=f"Q{i} [{q.difficulty}]: {q.text}".encode('latin-1', 'replace').decode('latin-1'))
            pdf.multi_cell(0, 8, txt=f"A: {q.option_a} | B: {q.option_b} | C: {q.option_c} | D: {q.option_d}".encode('latin-1', 'replace').decode('latin-1'))
            pdf.multi_cell(0, 8, txt=f"Correct: {q.correct_option} | Exp: {q.explanation or 'None'}".encode('latin-1', 'replace').decode('latin-1'))
            pdf.ln(5)

        return Response(
            bytes(pdf.output(dest='S'), 'latin-1'),
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment;filename={subject.replace(' ', '_')}_questions.pdf"}
        )'''

# Replace download_attempts_csv with pdf equivalent
csv_attempts_func = '''    @app.route("/download/all-attempts/csv")
    @login_required
    def download_attempts_csv():
        user_id = session["user_id"]
        attempts = QuizAttempt.query.filter_by(user_id=user_id).order_by(QuizAttempt.date_taken.desc()).all()
        
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Quiz Attempts Report"])
        writer.writerow(["Student", session.get("username")])
        writer.writerow([])
        writer.writerow(["Date", "Subject", "Total Q", "Correct", "Percentage", "Time"])
        
        for attempt in attempts:
            writer.writerow([
                attempt.date_taken,
                attempt.subject,
                attempt.total_questions,
                attempt.correct_answers,
                f"{attempt.percentage}%",
                f"{attempt.time_taken // 60}m"
            ])

        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=quiz_attempts.csv"}
        )'''

pdf_attempts_func = '''    @app.route("/download/all-attempts/pdf")
    @login_required
    def download_attempts_pdf():
        user_id = session["user_id"]
        attempts = QuizAttempt.query.filter_by(user_id=user_id).order_by(QuizAttempt.date_taken.desc()).all()
        
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="Quiz Attempts Report", ln=True, align="C")
        pdf.ln(5)
        pdf.cell(200, 10, txt=f"Student Name: {session.get('username')}", ln=True)
        pdf.ln(5)
        
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(50, 10, "Date", border=1)
        pdf.cell(40, 10, "Subject", border=1)
        pdf.cell(20, 10, "Total Q", border=1)
        pdf.cell(20, 10, "Correct", border=1)
        pdf.cell(30, 10, "Percentage", border=1)
        pdf.cell(30, 10, "Time", border=1)
        pdf.ln(10)
        
        pdf.set_font("Arial", size=10)
        for attempt in attempts:
            pdf.cell(50, 10, str(attempt.date_taken)[:19], border=1)
            pdf.cell(40, 10, str(attempt.subject)[:20], border=1)
            pdf.cell(20, 10, str(attempt.total_questions), border=1)
            pdf.cell(20, 10, str(attempt.correct_answers), border=1)
            pdf.cell(30, 10, f"{attempt.percentage}%", border=1)
            pdf.cell(30, 10, f"{attempt.time_taken // 60}m", border=1)
            pdf.ln(10)

        return Response(
            bytes(pdf.output(dest='S'), 'latin-1'),
            mimetype="application/pdf",
            headers={"Content-Disposition": "attachment;filename=quiz_attempts.pdf"}
        )'''

content = content.replace(csv_result_func, pdf_result_func)
content = content.replace(csv_questions_func, pdf_questions_func)
content = content.replace(csv_attempts_func, pdf_attempts_func)

# Add PDF Question upload and PDF student question bank download
new_routes = '''

    @app.route("/admin/questions/upload_pdf", methods=["POST"])
    @login_required
    @admin_required
    def admin_upload_questions_pdf():
        subject = request.form.get("subject", SUBJECTS[0])
        difficulty = request.form.get("difficulty", "Medium")
        
        if 'pdf_file' not in request.files:
            flash("No file part", "error")
            return redirect(url_for('admin'))
            
        file = request.files['pdf_file']
        if file.filename == '':
            flash("No selected file", "error")
            return redirect(url_for('admin'))
            
        if file and file.filename.endswith('.pdf'):
            try:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\\n"
                
                # Basic parsing logic: Split by lines, assume each line is a question
                lines = [line.strip() for line in text.split('\\n') if line.strip()]
                added = 0
                for line in lines:
                    if len(line) > 10:
                        question = Question(
                            subject=subject,
                            difficulty=difficulty,
                            text=line[:500],
                            option_a="A",
                            option_b="B",
                            option_c="C",
                            option_d="D",
                            correct_option="A",
                            explanation="Extracted from PDF"
                        )
                        db.session.add(question)
                        added += 1
                        
                db.session.commit()
                flash(f"Successfully extracted and added {added} questions.", "success")
            except Exception as e:
                flash(f"Error reading PDF: {str(e)}", "error")
        else:
            flash("Invalid file format. Please upload a PDF.", "error")
            
        return redirect(url_for('admin'))

    @app.route("/dashboard/download_question_bank_pdf")
    @login_required
    def download_question_bank_pdf():
        questions = Question.query.all()
        if not questions:
            flash("No questions found in the bank.", "error")
            return redirect(url_for("dashboard"))

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="Complete Question Bank", ln=True, align="C")
        pdf.ln(5)
        
        pdf.set_font("Arial", size=10)
        for i, q in enumerate(questions[:200], 1): # Limit to 200 to prevent huge PDFs
            pdf.multi_cell(0, 8, txt=f"Q{i} [{q.subject} - {q.difficulty}]: {q.text}".encode('latin-1', 'replace').decode('latin-1'))
            pdf.multi_cell(0, 8, txt=f"A: {q.option_a} | B: {q.option_b} | C: {q.option_c} | D: {q.option_d}".encode('latin-1', 'replace').decode('latin-1'))
            pdf.multi_cell(0, 8, txt=f"Correct: {q.correct_option}".encode('latin-1', 'replace').decode('latin-1'))
            pdf.ln(5)

        return Response(
            bytes(pdf.output(dest='S'), 'latin-1'),
            mimetype="application/pdf",
            headers={"Content-Disposition": "attachment;filename=question_bank.pdf"}
        )
'''

# Insert new routes before dashboard_stats
content = content.replace('def dashboard_stats(user_id):', new_routes + '\n\ndef dashboard_stats(user_id):')

with open('server.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patching complete.")
