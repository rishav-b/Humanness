import streamlit as st
import pandas as pd
import numpy as np
import io
import os
import threading
import logging
import base64
import scipy.stats as stats
from pypdf import PdfReader, PdfWriter
from pypdf.constants import UserAccessPermissions
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from PIL import Image as PILImage
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    Paragraph,
    PageBreak,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from pathlib import Path
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.piecharts import Pie
from itertools import combinations

APP_DIR = Path(__file__).resolve().parent
IMAGES_DIR = APP_DIR / "images"
FONTS_DIR = APP_DIR / "fonts"
LOGGER = logging.getLogger(__name__)

if "expd" not in st.session_state:
    st.session_state.expd = pd.DataFrame( 
            data = {
            "Cohort #": [],
            "# Positive Samples": [],
            "# Negative Samples": [],
            "Train/Test": [],
            },
        )

if "cq" not in st.session_state:
    st.session_state.cq = [0,0,0]

if "animate_slide" not in st.session_state:
    st.session_state.animate_slide = False

if "responses" not in st.session_state:
    st.session_state.responses = [{}, {}, {}]

st.set_page_config(
    page_title="COMPASS Humanness Calculator",
    page_icon="",
    layout="centered"
)

st.header("COMPASS Humanness Calculator")
st.text("Human-derived does not automatically mean human-relevant. The COMPASS TRUST-NAM Calculator provides a transparent, interoperable framework for benchmarking **Humanness, Relevance, and NAM Fidelity using cohort-anchored human evidence. Complete one or all three modules, generate quantitative scores, and download a publication-ready TRUST-NAM Benchmarking Report for reporting, comparison, and translational assessment." \
"TRUST-NAM is the benchmarking framework; COMPASS is the web platform that implements it. Complete individual modules or all three to generate an integrated TRUST-NAM report.")


st.markdown(
    """
    <style>
    h1, h2, h3 {
        color: rgb(8, 38, 74) !important;
    }

    h3 {
        font-size: 16px !important;
        text-transform: uppercase !important;
        letter-spacing: 1.32px !important;
    }

    @keyframes slideInRight {
        0% {
            opacity: 0;
            transform: translateX(40px);
        }
        100% {
            opacity: 1;
            transform: translateX(0);
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)




class Question:
    def __init__(self, question_id, input_renderers, scorer):
        self.question_id = question_id
        self.inputs = []
        self.input_renderers = input_renderers
        self.scorer = scorer
        self.page = 0
        self.num_questions = 0

    def get_score(self):
        return self.scorer(self.inputs)
    
    def render_question(self):
        
        st.markdown(
            f"""
            <style>
            div[data-testid="stVerticalBlock"]:has(> div.element-container [data-testid="stHeader"] + div),
            .st-key-slide_box_{self.page}_{st.session_state.cq[self.page]} {{
                animation: slideInRight 0.35s cubic-bezier(0.16, 1, 0.3, 1) forwards !important;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )

        restart, advance, spacer = st.columns([1, 1, 10])

        with restart:
            st.button(":material/restart_alt:", key=f"restart_btn_{self.page}_{st.session_state.cq[self.page]}",
                      on_click=self.restart)

        with advance:
            st.button(":material/arrow_forward:", key=f"next_btn_{self.page}_{st.session_state.cq[self.page]}",
                on_click=self.advance, disabled = st.session_state.cq[self.page] == self.num_questions
            )

        with st.container(key = f"slide_box_{self.page}_{st.session_state.cq[self.page]}", border=True):
            self.inputs = [r() for r in self.input_renderers]

        st.session_state.animate_slide = False
    
    def advance(self):
        st.session_state.animate_slide = True
        st.session_state.cq[self.page] = min(st.session_state.cq[self.page] + 1, self.num_questions-1)
        st.session_state.responses[self.page][self.question_id] = (self.inputs, self.get_score())

    def restart(self):
        st.session_state.cq[self.page] = 0
        st.session_state.responses[self.page] = {}

class Questionnaire:
    def __init__(self, questions: list[Question], page):
        self.questions = questions
        self.page = page

        for q in self.questions:
            q.num_questions = len(self.questions)
            q.page = self.page
        
        self.questions[st.session_state.cq[self.page]].render_question()

def cohort_numbers(expd):
    """
    Computes variation among the cohorts in their composition
    Not needed according to PG
    """

    train_data = np.array([expd["# Positive Samples"].iloc[x]/(expd["# Positive Samples"].iloc[x]+expd["# Negative Samples"].iloc[x]) for x in range(len(expd)) if expd["Train/Test"].iloc[x] == "Train"])
    test_data = np.array([expd["# Positive Samples"].iloc[x]/(expd["# Positive Samples"].iloc[x]+expd["# Negative Samples"].iloc[x]) for x in range(len(expd)) if expd["Train/Test"].iloc[x] == "Test"])
    train_var = np.var(train_data, ddof = 1)
    test_var = np.var(test_data, ddof = 1)
    dfn = len(train_data)-1
    dfd = len(test_data)-1

    if len(train_data) + len(test_data) > 2:
        s_p = np.sqrt((dfn*train_var + dfd*test_var)/(dfn + dfd))

        d = np.abs(np.mean(train_data) - np.mean(test_data))/s_p
    else:
        d = np.nan
    
    f_stat = train_var / test_var
    p_val = 2 * min(stats.f.cdf(f_stat, dfn, dfd), stats.f.sf(f_stat, dfn, dfd))


    print(d)

def mde(expd):
    ALPHA = 0.05 #significance
    BETA = 0.2   #type ii error rate

    mde_d = (stats.norm.ppf(1-ALPHA/2) + stats.norm.ppf(1-BETA)) * np.sqrt(1/)

def score_expd(expd):
    SCORE = 0

    # Humanness Q4 
    if len(expd) < 500:
        SCORE += 5
    elif len(expd) < 1000:
        SCORE += 10
    elif len(expd) < 5000:
        SCORE += 15
    elif len(expd) < 10000:
        SCORE += 20
    else: 
        SCORE += 25

    # Relevance Q1
    g1 = sum(expd["# Positive Samples"]) 
    g2 = sum(expd["# Negative Samples"])
    p = g1/(g1 + g2)

    if p == 0 or p == 1:
        SCORE += 5
    elif p < 0.5:
        SCORE += 15
    else:
        SCORE += 25

    return SCORE
    
def score_aucs(inputs):
    """
    Not finalized
    """
    def hanley_mcneil(inputs, n_pos, n_neg):
        inputs = np.array(inputs)
        n_pos = np.array(n_pos)
        n_neg = np.array(n_neg)
        
        q1 = inputs / (2.0 - inputs)
        q2 = (2.0 * (inputs**2)) / (1.0 + inputs)

        variance = (
            inputs * (1.0 - inputs)
            + (n_pos - 1) * (q1 - inputs**2)
            + (n_neg - 1) * (q2 - inputs**2)
        ) / n_pos / n_neg

        return np.sqrt(variance)
    
    expd = st.session_state.expd

    inputs = np.clip(inputs, 1e-4, 1.0 - 1e-4)
    
    train_aucs = np.array([inputs[x] for x in range(len(inputs)) if expd.iloc[x]["Train/Test"] == "Train"])
    test_aucs = np.array([inputs[x] for x in range(len(inputs)) if expd.iloc[x]["Train/Test"] == "Test"])

    train_ses = hanley_mcneil(train_aucs, expd.loc[expd["Train/Test"] == "Train", "# Positive Samples"].values, expd.loc[expd["Train/Test"] == "Train", "# Negative Samples"].values)
    test_ses = hanley_mcneil(test_aucs, expd.loc[expd["Train/Test"] == "Test", "# Positive Samples"].values, expd.loc[expd["Train/Test"] == "Test", "# Negative Samples"].values)

    feff_train_auc = np.sum(1/(train_ses)**2 * train_aucs) / np.sum(1/(train_ses)**2)
    feff_test_auc = np.sum(1/(test_ses)**2 * test_aucs) / np.sum(1/(test_ses)**2)

    train_chi_sq = np.sum(1/(train_ses)**2 * (train_aucs - feff_train_auc)**2)
    test_chi_sq = np.sum(1/(test_ses)**2 * (test_aucs - feff_test_auc)**2)

    train_p = 1 - stats.chi2.cdf(train_chi_sq, df = len(train_aucs)-1)
    test_p = 1 - stats.chi2.cdf(test_chi_sq, df = len(test_aucs)-1)

    def pooled_auc_and_var(aucs, ses, chi_sq, p_val, alpha=0.05):
        weights = 1.0 / (ses**2)
        if p_val < alpha:
            k = len(aucs)
            c = np.sum(weights) - np.sum(weights**2) / np.sum(weights)
            tau_sq = max(0, (chi_sq - k + 1) / c)
            weights = 1.0 / (ses**2 + tau_sq)
        pooled = np.sum(weights * aucs) / np.sum(weights)
        var = 1.0 / np.sum(weights)
        return pooled, var
    
    train_wauc, train_wauc_var = pooled_auc_and_var(train_aucs, train_ses, train_chi_sq, train_p)
    test_wauc, test_wauc_var = pooled_auc_and_var(test_aucs, test_ses, test_chi_sq, test_p)

    se_diff = np.sqrt(train_wauc_var + test_wauc_var)

    perf_drop = max(0, train_wauc-test_wauc)
    perf_drop_z = perf_drop/se_diff


    # Parameters to consider for final score:

    # perf_drop : Drop in performance between train and test
    # perf_drop_z : Significance of the drop
    # tau_sq : Variance between cohorts within either train or test
    # train_chi_sq, train_p : How variable AUC performance is across train cohorts and its significance
    # test_chi_sq, test_p : How variable AUC performance is across test cohorts and its significance


    #Temporary return statement for testing we need to figure out how to weight all these different parameters
    return perf_drop

def score(inputs):
    SCORE = 0
    score_dict = {
        "Yes, prospectively validated": 25,
        "Yes, retrospectively validated": 15, 
        "Exploratory association only": 5, 
        "No outcome association": 0,

        ">5 cohorts": 25,
        "3-5 cohorts": 15,
        "1-2 cohorts": 10,
        "Retrospective only": 5,
        "No outcome-linked cohorts": 0

    }

    for i in inputs:
        try:
            SCORE += score_dict[i]
        except KeyError:
            pass
    
    return SCORE

def get_humanness_interpretation(score):
    """
    Gives a simple interpretation based on current humanness score.
    This can be refined later as the calculator matures.
    """

    if score >= 80:
        return "High humanness: the model appears strongly anchored to human biology."
    elif score >= 60:
        return "Moderate-to-high humanness: the model has substantial human relevance."
    elif score >= 40:
        return "Partial humanness: the model has meaningful human relevance but important gaps remain."
    elif score >= 20:
        return "Low-to-moderate humanness: the model has some human anchoring but limited validation."
    else:
        return "Low humanness: the current evidence for human biological relevance is limited."
    
def get_relevance_interpretation(score):
    if score >= 80:
        return "Strongly clinically relevant."
    elif score >= 60:
        return "Moderately relevant."
    elif score >= 40:
        return "Weakly relevant."
    else:
        return "Limited translational relevance."

def generate_pdf_report(h_resp, r_resp, n_resp, h_score, r_score, n_score, user_id):
    cohort_numbers(expd)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    
    pdfmetrics.registerFont(TTFont('Inter-Bold', str(FONTS_DIR / 'Inter-Bold.ttf')))
    pdfmetrics.registerFont(TTFont('Inter-Medium', str(FONTS_DIR / 'Inter-Medium.ttf')))
    registerFontFamily("Inter", normal = "Inter-Medium", bold = "Inter-Bold")
    
    styles = getSampleStyleSheet()

    def render_metric(image_name, color, score, resp, score_name, score_desc):
        image_path = IMAGES_DIR / image_name
        with PILImage.open(image_path) as pil_img:
            source_width, source_height = pil_img.size

        max_width = 95
        max_height = 100
        scale = min(
            max_width / source_width,
            max_height / source_height,
        )
        image = Image(
            str(image_path),
            width=source_width * scale,
            height=source_height * scale,
            mask="auto",
        )
        pie = render_pie(score, color, resp)
        title = Paragraph(score_name, ParagraphStyle('ScoreTitle', parent=styles['Heading2'], fontSize=16, leading=20, textColor=colors.Color(color[0]/255, color[1]/255, color[2]/255, alpha=color[3]/255), alignment=1, fontName = "Inter-Bold"))
        description = Paragraph(score_desc, ParagraphStyle('ScoreDescription', parent=styles['Normal'], fontSize=12, leading=16, textColor=colors.Color(color[0]/255, color[1]/255, color[2]/255, alpha=color[3]/255), alignment=1, fontName = "Inter-Medium"))

        data = [[image, [title, Spacer(1, 6), description], pie]]

        col_widths = [150, 200, 175]



        box_table = Table(data, colWidths = col_widths)
        box_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1.5, colors.Color(color[0]/255, color[1]/255, color[2]/255, alpha=color[3]/255)),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ROUNDEDCORNERS', [10, 10, 10, 10]), 
        ]))

        box_table.spaceBefore = 10
        box_table.spaceAfter = 10


        return box_table
    
    heading_style = ParagraphStyle(
        'SectionHeading', parent=styles['Heading2'], fontSize=14, leading=18, fontName='Inter-Bold',
        textColor=colors.HexColor('#1E3A8A'), spaceBefore=16, spaceAfter=8, keepWithNext=True
    )
    body_style = ParagraphStyle(
        'BodyTextCustom', parent=styles['Normal'], fontSize=10, leading=14, fontName='Inter-Medium',
        textColor=colors.HexColor('#334155')
    )
    bold_style = ParagraphStyle(
        'BoldTextCustom', parent=body_style, fontName='Inter-Bold'
    )
    
    story = []

    def render_pie(score, color, resp):
        chart_drawing = Drawing(width=400, height=120)

        pc = Pie()
        pc.x = 150         
        pc.y = 10        
        pc.width = 100      
        pc.height = 100 
        pc.data = [35, 25, 20, 20]

        pc.innerRadiusFraction = 0.75 
        chart_drawing.add(pc)

        if not resp:
            pc.data = [100, 0]
        else:
            data = [value[1] for key, value in resp.items()]
            data.append(100 - sum(data))
            data.sort(reverse=True)
            pc.data = data

        for i in range(0, len(pc.data)):
            pc.slices[i].fillColor = colors.Color(color[0]/255, color[1]/255, color[2]/255, alpha=color[3]/255 * i/(len(pc.data)-1) if len(pc.data) > 1 else 1)


        center_text = String(
            pc.x + (pc.width / 2), 
            pc.y + (pc.height / 2) - 12,            
            f"{score}",        
            textAnchor='middle',     
            fontName='Helvetica-Bold',
            fontSize=36,
            fillColor= colors.Color(color[0]/255, color[1]/255, color[2]/255, alpha=color[3]/255)
        )
        chart_drawing.add(center_text)

        return chart_drawing
    
    story.append(Spacer(1, 75))
    story.append(render_metric("human.png", (30, 75, 150, 255), h_score, h_resp, "HUMANNESS SCORE", "Measures how strongly a discovery or model is anchored in real human biology."))
    story.append(render_metric("relevance.png", (80, 120, 60, 255), r_score, r_resp, "RELEVANCE SCORE", "Measures how closely a model connects to clinically meaningful disease states, outcomes, and treatment responses."))
    story.append(render_metric("nam.png", (200, 150, 60, 255), n_score, n_resp, "NAM FIDELITY SCORE", "Measures how faithfully and reproducibly a NAM captures human disease biology in a scalable, fit-for-purpose manner."))

    story.append(PageBreak())

    user_data = [[Paragraph("<b>Information</b>", bold_style), Paragraph("", body_style)]] + [ 
        [Paragraph(f"<b>{ukey.capitalize()}</b>", bold_style), Paragraph(f"{uvalue}", body_style)] for ukey, uvalue in user_id.items()
    ]
    
    user_data_table = Table(user_data, colWidths=[265, 265])
    user_data_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
    ]))

    story.append(Paragraph("Recipient Information", heading_style))

    story.append(user_data_table)

    story.append(Spacer(1, 10))

    story.append(Paragraph("Score Summary", heading_style))

    summary_data = [
        [Paragraph("<b>Index Module</b>", bold_style), Paragraph("<b>Score</b>", bold_style), Paragraph("<b>Classification Benchmark</b>", bold_style)],
        [Paragraph("Humanness Index", body_style), Paragraph(f"<b>{h_score}%</b>", body_style), Paragraph(get_humanness_interpretation(h_score), body_style)],
        [Paragraph("Relevance Index", body_style), Paragraph(f"<b>{r_score}%</b>", body_style), Paragraph(get_relevance_interpretation(r_score), body_style)],
        [Paragraph("NAM Fidelity Index", body_style), Paragraph(f"<b>{n_score}%</b>", body_style), Paragraph("Evaluated biological fidelity and translational consistency.", body_style)]
    ]
    
    summary_table = Table(summary_data, colWidths=[130, 60, 340])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
    ]))

    story.append(summary_table)

    story.append(PageBreak())
    
    # Helper to clean and build response logs
    def append_breakdown(title, module_responses):
        story.append(Paragraph(title, heading_style))
        table_data = [[Paragraph("<b>Question/Section</b>", bold_style), Paragraph("<b>Selected Evaluation</b>", bold_style), Paragraph("<b>Score</b>", bold_style)]]
        footnotes = {}

        for key, value in module_responses.items():
            table_data.append([
                Paragraph(key, body_style),
                Paragraph(",".join([str(v) for v in value[0]]), body_style),
                Paragraph((str(value[1])), body_style)
            ])
                    
        if len(table_data) > 1:
            t = Table(table_data, colWidths=[280, 170, 80])
            t.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                ('TOPPADDING', (0,0), (-1,-1), 6),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ]))
            story.append(t)
        else:
            story.append(Paragraph("No active answers recorded for this category.", body_style))

        story.append(Spacer(1,30))
        for v in set(footnotes.values()):
            story.append(Paragraph(v, body_style))
        story.append(PageBreak())
            
    append_breakdown("1. Humanness Index Breakdown", h_resp)
    append_breakdown("2. Relevance Index Breakdown", r_resp)
    append_breakdown("3. NAM Fidelity Index Breakdown", n_resp)

    def draw_front(canvas, doc):
        canvas.saveState()

        canvas.drawImage(IMAGES_DIR / "trustnam_header.png", 0, doc.pagesize[1] - 100, width=500, height=100, mask='auto')

        canvas.drawImage(IMAGES_DIR / "inetmed_letterhead.png", 40, 30, width=160, height=64, mask='auto')
        
        canvas.restoreState()

    def draw_later(canvas, doc):
        canvas.saveState()

        canvas.drawImage(IMAGES_DIR / "inetmed_letterhead.png", 40, 30, width=160, height=64, mask='auto')
        
        canvas.restoreState()

    
    doc.build(story, onFirstPage=draw_front, onLaterPages=draw_later)
    buffer.seek(0)
    input_stream = io.BytesIO(buffer.getvalue())
    reader = PdfReader(input_stream)
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)
    

    writer.encrypt(
        user_password="", 
        owner_password="iwhfuwehfpejoie", 
        permissions_flag= UserAccessPermissions.PRINT
    )
    
    output_stream = io.BytesIO()
    writer.write(output_stream)
    return output_stream.getvalue()

USER_SUBMISSION_FIELDS = (
    "submitted_at_utc",
    "first_name",
    "last_name",
    "email",
    "institution",
    "purpose",
)
CSV_WRITE_LOCK = threading.Lock()


def get_user_submissions_file():
    """Choose a persistent Railway Volume path when one is available."""
    configured_file = os.environ.get("USER_SUBMISSIONS_FILE", "").strip()
    if configured_file:
        return Path(configured_file).expanduser()

    railway_volume = os.environ.get(
        "RAILWAY_VOLUME_MOUNT_PATH", ""
    ).strip()
    if railway_volume:
        return Path(railway_volume) / "user_submissions.csv"

    return APP_DIR / "data" / "user_submissions.csv"


def safe_csv_value(value):
    """Prevent spreadsheet programs from treating user text as a formula."""
    text = str(value or "").strip()
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def get_csv_storage_error_message(error):
    """Return an actionable storage message without exposing user data."""
    if isinstance(error, PermissionError):
        return (
            "The app cannot write to its user-data folder. On Railway, "
            "attach a Volume to the service and mount it at /data."
        )
    return (
        "Your information could not be saved to the CSV file. Check the "
        "Railway Volume and deployment logs, then try again."
    )


def save_user_submission(user_id):
    """Append one completed user-information form to a local CSV file."""
    csv_file = get_user_submissions_file()
    row = {
        "submitted_at_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        ),
        "first_name": safe_csv_value(user_id.get("first name")),
        "last_name": safe_csv_value(user_id.get("last name")),
        "email": safe_csv_value(user_id.get("email")),
        "institution": safe_csv_value(user_id.get("institution")),
        "purpose": safe_csv_value(user_id.get("purpose")),
    }

    with CSV_WRITE_LOCK:
        csv_file.parent.mkdir(parents=True, exist_ok=True)
        write_header = (
            not csv_file.exists() or csv_file.stat().st_size == 0
        )
        with csv_file.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=USER_SUBMISSION_FIELDS,
            )
            if write_header:
                writer.writeheader()
            writer.writerow(row)


def get_user_id():
    with st.form("my_form"):
        fname = st.text_input("First Name:")
        lname = st.text_input("Last Name:")
        email = st.text_input("Email:")
        institution = st.text_input("Institution:")
        purpose = st.text_area("Purpose of Use:")
        submitted = st.form_submit_button("Submit")

    user_id = {
        "first name": fname,
        "last name": lname,
        "email": email,
        "institution": institution,
        "purpose": purpose,
    }

    form_complete = all(
        str(value).strip() for value in user_id.values()
    )

    if submitted:
        if form_complete:
            try:
                save_user_submission(user_id)
                st.session_state["saved_user_signature"] = tuple(
                    str(value).strip() for value in user_id.values()
                )
                st.success("Your information was saved.")
            except Exception as error:
                LOGGER.exception("Unable to save user submission")
                st.session_state.pop("saved_user_signature", None)
                st.error(get_csv_storage_error_message(error))
        else:
            st.session_state.pop("saved_user_signature", None)
            st.error("Please complete every field before submitting.")

    current_signature = tuple(
        str(value).strip() for value in user_id.values()
    )
    submission_saved = (
        st.session_state.get("saved_user_signature")
        == current_signature
    )

    return user_id, submission_saved

def generate_csv_files():
    csv_data = {
        "Humanness": st.session_state.responses[0],
        "Relevance": st.session_state.responses[1],
        "NAM Fidelity": st.session_state.responses[2]
    }
    for module, data in csv_data.items():
        df = pd.DataFrame.from_dict(data, orient='index')
        df.to_csv(f"{module}_responses.csv")

if st.query_params.get("page") != "calculator":
    st.markdown(
        """
        <style>
            @import url("https://fonts.googleapis.com/css2?family=Roboto:wght@500&display=swap");

            .stApp {
                background: #ffffff;
            }

            [data-testid="stHeader"] {
                display: none;
            }

            .block-container {
                max-width: 100%;
                margin: 0;
                padding: 0 0 2rem !important;
            }

            .landing-link {
                display: block;
                width: 100%;
                color: inherit;
                text-decoration: none;
            }

            .landing-link img {
                display: block;
                width: 100%;
                height: auto;
                object-fit: contain;
            }

            .landing-cta {
                padding: 1rem 1.5rem;
                background: #ffffff;
                color: #123b86;
                font-family: "Roboto";
                font-size: clamp(1.1rem, 2vw, 1.5rem);
                font-weight: 500;
                letter-spacing: 0.01em;
                text-align: center;
            }

            .landing-link:hover .landing-cta {
                background: #0a7f8f;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    landing_image = IMAGES_DIR / "website_picture.png"
    landing_image_data = base64.b64encode(landing_image.read_bytes()).decode("ascii")
    st.markdown(
        f'<a class="landing-link" href="?page=calculator" target="_self" '
        f'aria-label="Launch the Humanness calculator">'
        f'<img src="data:image/png;base64,{landing_image_data}" '
        f'alt="TRUST-NAM framework and report card">'
        f'<div class="landing-cta">Click anywhere to launch the calculator</div>'
        f"</a>",
        unsafe_allow_html=True,
    )
    st.stop()

expd, hum, rel, nam, pdf = st.tabs(["Experimental Design", "Humanness", "Relevance", "NAM Fidelity", "PDF Report"])

with expd:
    st.dataframe(st.session_state.expd)

    with st.container(border=True):
        g1 = st.number_input("# Positive Samples", min_value = 0)
        g2 = st.number_input("# Negative Samples", min_value = 0)
        t = st.selectbox(label="Train/Test", options = ["Train", "Test"])
        if st.button("+ Add Cohort", type = "primary"):
            expd = st.session_state.expd
            st.session_state.expd.loc[len(expd)] = {"Cohort #": len(expd)+1, "# Positive Samples": g1, "# Negative Samples": g2, "Train/Test": t}

            # cohort_numbers(st.session_state.expd)
            st.rerun()    

with hum:
    expd = st.session_state.expd
    h_questions = Questionnaire([Question("human_anchored", [lambda: st.selectbox("Was the original ML model built from human tissues or body fluids (blood, BAL, etc.)?", options = ("Yes", "No"))], lambda x: 5 if x[0] == "Yes" else 0),
                   Question("data_quality", [lambda: st.selectbox("What was the quality of the dataset(s) used to build the model?", options = ("High quality (Deep sequencing, > 50M reads/sample, validated platforms)", "Not high quality < 50M reads/sample or not validated"))], lambda x: 10 if "> 50M" in x[0] else 0),
                   Question("cross_species_conservation", [lambda: st.selectbox("Is the entity conserved across species? (foundational biology but not a substitute for humanness)", options = ("Yes", "No"))], lambda x: 5 if x[0] == "Yes" else 0),
                   Question("roc_auc", [lambda x=x: st.number_input(f"AUC of Cohort #{x+1} ({expd.iloc[x]["Train/Test"]} n = {int(expd.loc[expd["Cohort #"] == x+1]["# Positive Samples"].iloc[0])+int(expd.loc[expd["Cohort #"] == x+1]["# Negative Samples"].iloc[0])})", max_value= 1.0, key = str(x), format = "%.4f") for x in range(len(expd))], score_aucs)], 
                   
                   0)

with rel:
    expd = st.session_state.expd
    r_questions = Questionnaire([Question("disease_severity", [lambda: st.selectbox("Was the model originally built or independently validated to classify disease severity, progression, therapeutic response, relapse, survival, or clinical outcomes?", options = ("Yes, prospectively validated", "Yes, retrospectively validated", "Exploratory association only", "No outcome association"))], score),
                   Question("prospective_cohorts", [lambda: st.selectbox("Were datasets prospectively collected with future outcomes annotated after tissue diversion?", options = (">5 cohorts","3-5 cohorts","1-2 cohorts","Retrospective only","No outcome-linked cohorts"))], score),
                   Question("gwas", [lambda: st.selectbox("Is there additional support from GWAS and/or other biological support?", options = ("Yes", "No"))], lambda x: 25 if x[0] == "Yes" else 0)],
                   
                   1)
    
with pdf:
    user_id, submission_saved = get_user_id()

    pdf_bytes = generate_pdf_report(
        st.session_state.responses[0],
        st.session_state.responses[1],
        st.session_state.responses[2],
        sum([v[1] for k, v in st.session_state.responses[0].items()]),
        sum([v[1] for k, v in st.session_state.responses[1].items()]),
        sum([v[1] for k, v in st.session_state.responses[2].items()]),
        user_id
    )

    st.pdf(pdf_bytes)

    required_fields = (
        "first name",
        "last name",
        "email",
        "institution",
        "purpose",
    )
    form_complete = all(
        str(user_id.get(field, "")).strip()
        for field in required_fields
    )
    
    st.download_button(
        label="Download Publication PDF Summary ⬇",
        data=pdf_bytes,
        file_name="TRUST_NAM_Humanness_Assessment_Report.pdf",
        mime="application/pdf",
        disabled=not (form_complete and submission_saved),
        on_click="ignore",
    )
    