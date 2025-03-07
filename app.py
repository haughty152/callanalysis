import os
import speech_recognition as sr
from flask import Flask, request, render_template, redirect, url_for, send_file
from werkzeug.utils import secure_filename
from pydub import AudioSegment
from langdetect import detect
from deep_translator import GoogleTranslator
import pandas as pd
import re
from datetime import datetime

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'm4a'}

# Define the scorecard criteria and their weights
SCORECARD_CRITERIA = {
    'Agent Name': 0,
    'Type of call': 0,
    'Account number': 0,
    'Authentication': 20,
    'Business Disclaimer': 5,
    'Mention CCPI': 5,
    'CIF Confirmed': 10,
    'Method of Payment': 5,
    'Negotiation': 10,
    'Reason for Non-Payment': 10,
    'Forbearance': 10,
    'NCA Clause': 10,
    'Voice & Data': 5,
    'Recap the arrangement': 5,
    'Tone & Empathy with client': 5
}

# Keywords to look for in the transcription for each criterion
KEYWORDS = {
    'Agent Name': ['my name is', 'this is', 'speaking with', 'calling from'],
    'Type of call': ['outbound', 'inbound', 'regarding your account'],
    'Account number': ['account', 'regarding your account'],
    'Authentication': ['verify your details', 'date of birth', 'ID number', 'telephone number', 
                      'cell phone', 'residential address', 'postal address', 'company you work for'],
    'Business Disclaimer': ['recorded for quality', 'security purposes', 'registered credit provider'],
    'Mention CCPI': ['cash deposit', 'internet banking', 'atm transfer', 'bank transfer', 'paying at the selected stores'],
    'CIF Confirmed': ['confirm if we have your correct information', 'verify contact details', 
                     'postal and residential address', 'fica compliant'],
    'Method of Payment': ['method of payment', 'paying via', 'debit order', 'bank transfer', 'cash deposit'],
    'Negotiation': ['full payment', 'arrears amount', 'negotiate', 'instalment amount', 'minimum'],
    'Reason for Non-Payment': ['why did you fail to pay', 'reason for', 'non-payment', 'missed payment', 'short payment'],
    'Forbearance': ['forbearance', 'forbs', 'financial strain', 'unemployment letter', 'bank statement',
                   'proof of income', 'monthly expenditure'],
    'NCA Clause': ['legally required', 'credit record', 'credit bureau', 'missed or late payment', 'will affect this record'],
    'Voice & Data': ['clearly', 'audible', 'professional', 'articulate'],
    'Recap the arrangement': ['recap', 'confirm the', 'PTP date', 'amount', 'payment method', 'keeping their promise'],
    'Tone & Empathy': ['understand', 'appreciate', 'thank you', 'sorry to hear', 'assistance', 'help you']
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def convert_to_wav(filepath):
    audio = AudioSegment.from_file(filepath)
    wav_path = filepath.rsplit('.', 1)[0] + '.wav'
    audio.export(wav_path, format='wav')
    return wav_path

def transcribe_audio(filepath):
    recognizer = sr.Recognizer()
    with sr.AudioFile(filepath) as source:
        audio_data = recognizer.record(source)
    try:
        return recognizer.recognize_google(audio_data)
    except sr.UnknownValueError:
        return "Could not understand the audio"
    except sr.RequestError:
        return "Error connecting to the speech recognition service"

def process_text(text):
    sentences = text.split('.')
    processed_data = []
    for sentence in sentences:
        sentence = sentence.strip()
        if sentence:
            try:
                lang = detect(sentence)
            except:
                lang = "unknown"
            
            try:
                translation = GoogleTranslator(source='auto', target='en').translate(sentence) if lang != 'en' else sentence
            except:
                translation = sentence
                
            processed_data.append((sentence, lang, translation))
    return processed_data

def analyze_call_with_scorecard(text):
    analysis_data = []
    total_score = 0
    max_score = 100
    
    # Extract agent name, type of call, and account number for identification
    agent_name = extract_agent_name(text)
    call_type = "Outbound" if "outbound" in text.lower() or "calling from" in text.lower() else "Inbound"
    account_number = extract_account_number(text)
    
    # Score each criterion
    for criterion, weight in SCORECARD_CRITERIA.items():
        keywords = KEYWORDS.get(criterion, [])
        score = calculate_criterion_score(text, keywords, weight)
        
        # Special cases for information fields
        if criterion == 'Agent Name':
            comments = f"Agent identified as: {agent_name}"
            score_value = "Info"
        elif criterion == 'Type of call':
            comments = f"Call type: {call_type}"
            score_value = "Info"
        elif criterion == 'Account number':
            comments = f"Account mentioned: {account_number}"
            score_value = "Info"
        else:
            percentage = (score / weight * 100) if weight > 0 else 0
            if percentage >= 80:
                comments = "Excellent"
            elif percentage >= 60:
                comments = "Good"
            elif percentage >= 40:
                comments = "Average"
            else:
                comments = f"Needs improvement - Missing keywords: {', '.join(keywords)}"
            score_value = f"{score}/{weight} ({int(percentage)}%)"
            total_score += score
        
        analysis_data.append((criterion, score_value, comments))
    
    # Calculate overall performance
    overall_percentage = (total_score / (max_score - 0)) * 100  # Subtracting the weight of info fields
    
    # Add overall score
    analysis_data.append(("OVERALL SCORE", f"{total_score}/{max_score}", f"{int(overall_percentage)}% - {get_rating(overall_percentage)}"))
    
    # Generate improvement suggestions based on low-scoring criteria
    improvement_suggestions = generate_improvement_suggestions(analysis_data)
    
    return analysis_data, improvement_suggestions

def extract_agent_name(text):
    name_patterns = [
        r"my name is (\w+)",
        r"this is (\w+)",
        r"speaking with (\w+)"
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text.lower())
        if match:
            return match.group(1).capitalize()
    return "Unknown"

def extract_account_number(text):
    account_patterns = [
        r"account (\d+)",
        r"account number (\d+)",
        r"account #(\d+)"
    ]
    
    for pattern in account_patterns:
        match = re.search(pattern, text.lower())
        if match:
            return match.group(1)
    return "Not mentioned"

def calculate_criterion_score(text, keywords, max_score):
    if max_score == 0:  # For information fields
        return 0
        
    text_lower = text.lower()
    matches = sum(1 for keyword in keywords if keyword.lower() in text_lower)
    
    # Calculate score based on keyword matches
    if matches == 0:
        return 0
    elif matches == 1:
        return max_score * 0.5  # 50% for at least one keyword
    else:
        return max_score  # Full score for multiple keywords
    
def get_rating(percentage):
    if percentage >= 90:
        return "Excellent"
    elif percentage >= 80:
        return "Very Good"
    elif percentage >= 70:
        return "Good"
    elif percentage >= 60:
        return "Satisfactory"
    elif percentage >= 50:
        return "Needs Improvement"
    else:
        return "Unsatisfactory"

def generate_improvement_suggestions(analysis_data):
    suggestions = []
    
    # Exclude the overall score and info fields from consideration
    relevant_data = [item for item in analysis_data if item[0] not in ['OVERALL SCORE', 'Agent Name', 'Type of call', 'Account number']]
    
    for criterion, score, comments in relevant_data:
        if "Needs improvement" in comments:
            if criterion == 'Authentication':
                suggestions.append("Ensure you ask at least 2 CIF and 2 Non-CIF questions for proper authentication.")
            elif criterion == 'Business Disclaimer':
                suggestions.append("Always state that the call is being recorded for Quality and Security Purposes and that Absa Bank is a Registered Credit provider.")
            elif criterion == 'Mention CCPI':
                suggestions.append("Remember to discuss payment methods including CPPI (Paying at the selected stores).")
            elif criterion == 'CIF Confirmed':
                suggestions.append("Always verify and update customer details including postal and residential addresses.")
            elif criterion == 'Method of Payment':
                suggestions.append("Confirm specific method of payment (Cash deposit, internet banking, ATM transfer, Bank transfer, etc.).")
            elif criterion == 'Negotiation':
                suggestions.append("Follow the negotiation hierarchy: full arrears amount, then instalment amount, then minimum amount.")
            elif criterion == 'Reason for Non-Payment':
                suggestions.append("Directly ask for and document the specific reason for non-payment or short payment.")
            elif criterion == 'Forbearance':
                suggestions.append("For D2D-D5D accounts, offer forbearance plan and explain document requirements.")
            elif criterion == 'NCA Clause':
                suggestions.append("Include the NCA disclaimer about credit bureau reporting and consequences of missed payments.")
            elif criterion == 'Voice & Data':
                suggestions.append("Speak clearly and professionally throughout the call.")
            elif criterion == 'Recap the arrangement':
                suggestions.append("Always recap the payment details including date, amount and payment method.")
            elif criterion == 'Tone & Empathy with client':
                suggestions.append("Show more empathy and understanding in your conversation with clients.")
    
    # Add general suggestions if there aren't many specific ones
    if len(suggestions) < 3:
        general_suggestions = [
            "Follow the script sequence for all calls.",
            "Document call notes thoroughly after each interaction.",
            "Ensure you mention the consequences of non-payment clearly.",
            "Always be respectful and professional regardless of customer response."
        ]
        suggestions.extend(general_suggestions[:3 - len(suggestions)])
    
    return suggestions[:5]  # Return top 5 suggestions

def save_to_excel(data, analysis_data, improvement_suggestions, original_text, call_metadata=None):
    # Create a timestamp for the report
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Create an Excel writer
    excel_path = os.path.join(UPLOAD_FOLDER, 'call_analysis.xlsx')
    writer = pd.ExcelWriter(excel_path, engine='xlsxwriter')
    
    # Get the workbook and create a format for headers
    workbook = writer.book
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#D3D3D3',
        'border': 1
    })
    
    # Format for the overall score section
    overall_format = workbook.add_format({
        'bold': True,
        'font_size': 14,
        'align': 'center',
        'valign': 'vcenter',
        'bg_color': '#B8CCE4',
        'border': 1
    })
    
    # Create a cover sheet with call information
    call_info_data = []
    if call_metadata:
        for key, value in call_metadata.items():
            call_info_data.append([key, value])
    else:
        call_info_data = [
            ["Analysis Date", timestamp],
            ["Analysis Type", "Call Quality Assessment"],
            ["File Analyzed", call_metadata.get("filename", "Unknown")],
        ]
        
        # Extract some basic metrics from the analysis data
        for item in analysis_data:
            if item[0] == "Agent Name":
                call_info_data.append(["Agent", item[2].replace("Agent identified as: ", "")])
            elif item[0] == "Type of call":
                call_info_data.append(["Call Type", item[2].replace("Call type: ", "")])
            elif item[0] == "Account number":
                call_info_data.append(["Account", item[2].replace("Account mentioned: ", "")])
            elif item[0] == "OVERALL SCORE":
                call_info_data.append(["Overall Score", item[2]])
    
    # Add the full transcript
    call_info_data.append(["Full Transcript", original_text])
    
    df_info = pd.DataFrame(call_info_data, columns=["Field", "Value"])
    df_info.to_excel(writer, sheet_name='Call Information', index=False)
    
    # Format the Call Information sheet
    worksheet = writer.sheets['Call Information']
    worksheet.set_column('A:A', 20)
    worksheet.set_column('B:B', 80)
    
    # Transcription Sheet
    df_transcription = pd.DataFrame(data, columns=['Original Text', 'Detected Language', 'English Translation'])
    df_transcription.to_excel(writer, sheet_name='Transcription', index=False)
    
    # Format the transcription sheet
    worksheet = writer.sheets['Transcription']
    worksheet.set_column('A:A', 50)
    worksheet.set_column('B:B', 15)
    worksheet.set_column('C:C', 50)
    
    # Apply header format
    for col_num, value in enumerate(df_transcription.columns.values):
        worksheet.write(0, col_num, value, header_format)
    
    # Scorecard Sheet
    df_analysis = pd.DataFrame(analysis_data, columns=['Criterion', 'Score', 'Comments'])
    
    # Create special formatting for the scorecard
    df_analysis.to_excel(writer, sheet_name='Scorecard', index=False)
    worksheet = writer.sheets['Scorecard']
    
    # Format the scorecard sheet
    worksheet.set_column('A:A', 30)
    worksheet.set_column('B:B', 20)
    worksheet.set_column('C:C', 50)
    
    # Apply header format
    for col_num, value in enumerate(df_analysis.columns.values):
        worksheet.write(0, col_num, value, header_format)
    
    # Apply conditional formatting to the scorecard sheet
    excellent_format = workbook.add_format({'bg_color': '#C6EFCE'})  # Light green
    good_format = workbook.add_format({'bg_color': '#FFEB9C'})       # Light yellow
    needs_improvement_format = workbook.add_format({'bg_color': '#FFC7CE'})  # Light red
    
    # Add formats for each row based on the content
    for i, row in enumerate(analysis_data):
        criterion, score, comments = row
        row_idx = i + 1  # +1 because we have a header row
        
        if criterion == "OVERALL SCORE":
            # Merge cells and apply special format to overall score
            worksheet.merge_range(row_idx, 0, row_idx, 2, f"OVERALL SCORE: {comments}", overall_format)
        else:
            # Apply conditional formatting based on the comments
            if "Excellent" in comments:
                for col in range(3):
                    worksheet.write(row_idx, col, row[col], excellent_format)
            elif "Good" in comments or "Average" in comments:
                for col in range(3):
                    worksheet.write(row_idx, col, row[col], good_format)
            elif "Needs improvement" in comments:
                for col in range(3):
                    worksheet.write(row_idx, col, row[col], needs_improvement_format)
    
    # Improvement Plan Sheet
    df_improvement = pd.DataFrame({'Suggestions for Improvement': improvement_suggestions})
    df_improvement.to_excel(writer, sheet_name='Improvement Plan', index=False)
    
    # Format the improvement plan sheet
    worksheet = writer.sheets['Improvement Plan']
    worksheet.set_column('A:A', 80)
    
    # Apply header format
    worksheet.write(0, 0, 'Suggestions for Improvement', header_format)
    
    # Create a reference sheet with script and scorecard information
    script_data = [
        ["Script Section", "Description", "Importance"],
        ["Greeting", "Good morning/Afternoon/Good Evening, may I please speak to...", "Required"],
        ["Call and Business Disclosure", "This call is being recorded for Quality and Security Purposes...", "Required (5%)"],
        ["Authentication", "To ensure that I am speaking with the correct customer...", "Critical (20%)"],
        ["Reason for the Call", "Mention the problem - missed/short payment, broken promise...", "Required"],
        ["Obtaining reason for default", "Why did you fail to pay your instalment?", "Important (10%)"],
        ["Negotiation", "Request payments in descending order: 100%, 30%, 10%", "Important (10%)"],
        ["Forbearance", "Offer the forbs plan to account from D2D-D5D", "Important (10%)"],
        ["NCA Disclaimer", "ABSA is legally required to provide an update of your credit record...", "Important (10%)"],
        ["Payment Method", "Will you be paying via Cash deposit, internet banking...", "Required (5%)"],
        ["CIF Confirmation", "Could we please confirm if we have your correct information?", "Important (10%)"],
        ["Closing", "Recap the PTP date, amount, and payment method", "Required (5%)"]
    ]
    
    df_script = pd.DataFrame(script_data[1:], columns=script_data[0])
    df_script.to_excel(writer, sheet_name='Reference Guide', index=False)
    
    # Format the reference guide sheet
    worksheet = writer.sheets['Reference Guide']
    worksheet.set_column('A:A', 25)
    worksheet.set_column('B:B', 60)
    worksheet.set_column('C:C', 20)
    
    # Apply header format
    for col_num, value in enumerate(df_script.columns.values):
        worksheet.write(0, col_num, value, header_format)
    
    # Save the Excel file
    writer.close()
    
    return excel_path

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    data = None
    analysis_data = None
    improvement_suggestions = None
    audio_path = None
    excel_path = None
    original_text = None
    
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            audio_path = filepath  # Save path for playback
            
            if not filename.endswith('.wav'):
                filepath = convert_to_wav(filepath)
            
            original_text = transcribe_audio(filepath)
            processed_data = process_text(original_text)
            analysis_data, improvement_suggestions = analyze_call_with_scorecard(original_text)
            
            # Create call metadata
            call_metadata = {
                "filename": filename,
                "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "file_size": f"{os.path.getsize(filepath) / 1024:.2f} KB",
                "duration": "Unknown"  # Could calculate if needed
            }
            
            excel_path = save_to_excel(
                processed_data, 
                analysis_data, 
                improvement_suggestions, 
                original_text,
                call_metadata
            )
            
            return render_template('index.html', 
                                  data=processed_data, 
                                  analysis_data=analysis_data, 
                                  improvement_suggestions=improvement_suggestions, 
                                  excel_path=excel_path, 
                                  audio_path=audio_path,
                                  original_text=original_text)
    
    return render_template('index.html', 
                          data=data, 
                          analysis_data=analysis_data, 
                          improvement_suggestions=improvement_suggestions, 
                          audio_path=audio_path, 
                          excel_path=excel_path,
                          original_text=original_text)

@app.route('/download_excel')
def download_excel():
    excel_path = os.path.join(UPLOAD_FOLDER, 'call_analysis.xlsx')
    return send_file(excel_path, as_attachment=True, download_name='call_analysis.xlsx')

@app.route('/play_audio/<filename>')
def play_audio(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    return send_file(filepath)

if __name__ == '__main__':
    app.run(debug=True)