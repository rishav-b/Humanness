import streamlit as st
import pandas as pd
import numpy as np
import io
import re
import xml.etree.ElementTree as ET
import os
import threading
import logging
import base64
import math
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
    Flowable,
    PageBreak,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from pathlib import Path
from reportlab.graphics.shapes import Drawing, Circle, Line, String
from reportlab.graphics.charts.spider import SpiderChart
from reportlab.graphics.charts.piecharts import Pie

APP_DIR = Path(__file__).resolve().parent
IMAGES_DIR = APP_DIR / "images"
FONTS_DIR = APP_DIR / "fonts"
LOGGER = logging.getLogger(__name__)

if "control_name" not in st.session_state:
    st.session_state.control_name = "Control"

if "test_name" not in st.session_state:
    st.session_state.test_name = "Test"

if "expd" not in st.session_state:
    st.session_state.expd = pd.DataFrame( 
            data = {
            "Cohort #": [],
            f"# {st.session_state.test_name} Samples": [],
            f"# {st.session_state.control_name} Samples": [],
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
st.markdown(
    """
    Human-derived does not automatically mean human-relevant. The **COMPASS TRUST-NAM Calculator** provides a transparent, interoperable framework for benchmarking **Humanness, Relevance, and NAM Fidelity** using cohort-anchored human evidence. **Complete one or all three modules**, generate quantitative scores, and download a publication-ready TRUST-NAM Benchmarking Report for reporting, comparison, and translational assessment.
    
    *TRUST-NAM is the benchmarking framework; COMPASS is the web platform that implements it. Complete individual modules or all three to generate an integrated TRUST-NAM report*.
    """
)


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
    def __init__(self, question_id, question_descs, input_renderers, scorer, definitions = []):
        self.question_id = question_id
        self.question_descs = question_descs
        self.inputs = []
        self.input_renderers = input_renderers
        self.scorer = scorer
        self.definitions = definitions
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
            st.markdown(f"""<h3>{self.question_id}</h3>""", unsafe_allow_html=True)
            for i, q_lambda in enumerate(self.input_renderers):
                written_question = self.question_descs[i]
                for d in self.definitions:
                    if " "+d.text in self.question_descs[i] and d.definition_type == "label":
                        written_question = written_question.replace(" "+d.text, " "+d.render_definition())
                        
                    elif "-"+d.text in self.question_descs[i] and d.definition_type == "label":
                        written_question = written_question.replace("-"+d.text, "-"+d.render_definition())
                        
                st.write(written_question, unsafe_allow_html=True)
                
                self.inputs.append(self.input_renderers[i](label_visibility="collapsed", key=f"{self.page}_{self.question_id}_{i}"))

        st.session_state.animate_slide = False
    
    def advance(self):
        st.session_state.animate_slide = True
        st.session_state.cq[self.page] = min(st.session_state.cq[self.page] + 1, self.num_questions)
        st.session_state.responses[self.page][self.question_id] = (self.inputs, self.get_score())

    def restart(self):
        st.session_state.cq[self.page] = 0
        st.session_state.responses[self.page] = {}

class Definition:
    def __init__(self, text, definition, definition_type, in_pdf):
        self.text = text
        self.definition = definition
        self.definition_type = definition_type
        self.in_pdf = in_pdf

    def render_definition(self):
        st.markdown("""
            <style>
            .tooltip, .definition {
            position: relative;
            display: inline-block;
            border-bottom: 1px dotted #182B49; 
            color: #1677c8;
            cursor: pointer;
            }

            .tooltip .tooltiptext, .definition .definitiontext {
            visibility: hidden;
            width: 400px;
            font-size: 0.6em;
            font-weight: 400;
            background-color: #333;
            color: #fff;
            text-align: center;
            border-radius: 6px;
            padding: 8px;
            position: absolute;
            z-index: 1;
            bottom: 125%; 
            left: 50%;
            margin-left: -100px;
            opacity: 0;
            transition: opacity 0.3s;
            }
                    
            .definition .definitiontext {
                font-size: 12px;
            }

            .tooltip:hover .tooltiptext, .definition:hover .definitiontext {
            visibility: visible;
            opacity: 1;
            }
            </style>
            """, unsafe_allow_html=True)
        
        if self.definition_type == "title":
            return f"""<span class="tooltip">{self.text}<span class="tooltiptext">{self.definition}</span></span>"""
        else:
            return f"""<span class="definition">{self.text}<span class="definitiontext">{self.definition}</span></span>"""

class Questionnaire:
    def __init__(self, questions: list[Question], page):
        self.questions = questions
        self.page = page

        for q in self.questions:
            q.num_questions = len(self.questions)
            q.page = self.page

        if st.session_state.cq[self.page] == len(self.questions):
            file_names = ["human.svg", "relevance.svg", "nam.svg"]

            svg_markup, error = process_and_fill_svg(
                IMAGES_DIR / file_names[self.page],
                sum([v[1] for v in st.session_state.responses[self.page].values()]), 
                "#1677c8"      
            )

            if not error and svg_markup:
                score, image = st.columns([3,3])
                with score:
                    st.markdown(
                        f"""
                        <div style="display: flex; flex-direction: column; align-items: flex-start; width: 100%; margin-top: 20px;">
                            <div style="display: flex; align-items: center; gap: 20px; width: 100%; margin-bottom: 10px;">
                                <div style="width: 100px;"><h3 style="margin: 0; text-align: left;">Score</h3></div>
                                <div style="font-size: 24px; font-weight: bold; color: #1677c8;">
                                    {sum([v[1] for v in st.session_state.responses[self.page].values()])}%
                                </div>
                            </div>
                            <div style="display: flex; align-items: center; gap: 20px; width: 100%;">
                                <div style="width: 100px;"><h3 style="margin: 0; text-align: left;">Grade</h3></div>
                                <div style="font-size: 16px; font-weight: bold; color: #1677c8;">
                                    {get_interpretation(sum([v[1] for v in st.session_state.responses[self.page].values()]), self.page)}
                                </div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with image:
                    st.image(svg_markup, width='content')
        else:
            self.questions[st.session_state.cq[self.page]].render_question()

def get_interpretation(score, page):
    """
    Gives a simple interpretation based on current humanness score.
    This can be refined later as the calculator matures.
    """

    if page == 0:

        if score >= 80:
            return "High humanness, strongly anchored to human biology."
        elif score >= 60:
            return "Moderate-high humanness"
        elif score >= 40:
            return "Partial humanness, important gaps remain"
        elif score >= 20:
            return "Low, limited validation"
        else:
            return "Low, limited human biological relevance."
        
    elif page == 1:
        if score >= 80:
            return "Strongly clinically relevant."
        elif score >= 60:
            return "Moderately relevant."
        elif score >= 40:
            return "Weakly relevant."
        else:
            return "Limited translational relevance."
        
    else: 
        return "N/A"

def process_and_fill_svg(svg_filepath, percentage, color_hex):
    """
    Modifies an SVG so that it fills as a single cohesive unit from the bottom up,
    by using global canvas coordinates (userSpaceOnUse) for the gradient.
    """
    try:
        ET.register_namespace('', "http://www.w3.org/2000/svg")
        
        tree = ET.parse(svg_filepath)
        root = tree.getroot()
        
        color_hex = color_hex.lstrip('#')
        
        # 1. Extract dimensions to define the global height scale
        viewbox = root.get('viewBox')
        if viewbox:
            _, _, vb_w, vb_h = viewbox.split()
            width, height = float(vb_w), float(vb_h)
        else:
            width = float(root.get('width', '500').replace('px', ''))
            height = float(root.get('height', '500').replace('px', ''))

        # 2. Calculate exact absolute Y position where the color changes
        # SVG 0 is the very top, 'height' is the very bottom.
        split_y = height - (height * (percentage / 100))
        
        grad_id = "global_svg_grad"
        
        # 3. Use gradientUnits="userSpaceOnUse" and absolute coordinates (y1 -> y2)
        # This treats the whole SVG canvas as a single shared bucket.
        defs_markup = f"""
        <defs xmlns="http://www.w3.org/2000/svg">
            <linearGradient id="{grad_id}" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="{height}">
                <stop offset="0%" stop-color="#CCCCCC" stop-opacity="0.3" />
                <stop id="split-top" y-pos="{split_y}" offset="{split_y}" stop-color="#CCCCCC" stop-opacity="0.3" />
                <stop id="split-bottom" y-pos="{split_y}" offset="{split_y}" stop-color="#{color_hex}" stop-opacity="1" />
                <stop offset="100%" stop-color="#{color_hex}" stop-opacity="1" />
            </linearGradient>
        </defs>
        """
        
        # ElementTree requires percentages or fractional bounds for string offsets in basic parsers,
        # so we will inject the exact percentage representation of the global split point:
        split_percent = 100 - percentage
        
        defs_markup = f"""
        <defs xmlns="http://www.w3.org/2000/svg">
            <linearGradient id="{grad_id}" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="{height}">
                <stop offset="0%" stop-color="#CCCCCC" stop-opacity="0.3" />
                <stop offset="{split_percent}%" stop-color="#CCCCCC" stop-opacity="0.3" />
                <stop offset="{split_percent}%" stop-color="#{color_hex}" stop-opacity="1" />
                <stop offset="100%" stop-color="#{color_hex}" stop-opacity="1" />
            </linearGradient>
        </defs>
        """
        defs_element = ET.fromstring(defs_markup)
        
        # 4. Clean individual shape styles so they fall back to the parent container's fill rule
        def strip_fills(element):
            if 'fill' in element.attrib:
                del element.attrib['fill']
            if 'style' in element.attrib:
                style = element.attrib['style']
                style = re.sub(r'fill\s*:\s*[^;]+;?', '', style)
                element.attrib['style'] = style
            for child in element:
                strip_fills(child)

        root_children = list(root)
        global_group = ET.Element('g', {
            'id': 'cohesive_fill_group',
            'fill': f"url(#{grad_id})" 
        })
        
        for child in root_children:
            root.remove(child)
            strip_fills(child)
            global_group.append(child)
            
        root.append(defs_element)
        root.append(global_group)
        
        svg_string = ET.tostring(root, encoding='utf-8').decode('utf-8')
        return svg_string, None

    except Exception as e:
        return None, f"Error processing SVG: {str(e)}"

def cohort_numbers(expd):
    """
    Computes variation among the cohorts in their composition
    Not needed according to PG
    """

    train_data = np.array([expd[f"# {st.session_state.test_name} Samples"].iloc[x]/(expd[f"# {st.session_state.test_name} Samples"].iloc[x]+expd[f"# {st.session_state.control_name} Samples"].iloc[x]) for x in range(len(expd)) if expd["Train/Test"].iloc[x] == "Train"])
    test_data = np.array([expd[f"# {st.session_state.test_name} Samples"].iloc[x]/(expd[f"# {st.session_state.test_name} Samples"].iloc[x]+expd[f"# {st.session_state.control_name} Samples"].iloc[x]) for x in range(len(expd)) if expd["Train/Test"].iloc[x] == "Test"])
    train_var = np.var(train_data, ddof = 1)
    test_var = np.var(test_data, ddof = 1)
    dfn = len(train_data)-1
    dfd = len(test_data)-1

    if len(train_data) + len(test_data) > 2:
        s_p = np.sqrt((dfn*train_var + dfd*test_var)/(dfn + dfd))

        d = np.abs(np.mean(train_data) - np.mean(test_data))/s_p
    else:
        d = np.nan
    
    j = 1 - 3/(4*(dfn+dfd)-1)

    g = d * j

    #Hedge's g correction for Cohen's d
    return g


def score_expd(expd):
    q3 = 0
    # Humanness Q3-4 

    len_train = sum(expd[f"# {st.session_state.test_name} Samples"][expd["Train/Test"] == "Train"]) + sum(expd[f"# {st.session_state.control_name} Samples"][expd["Train/Test"] == "Train"])
    len_test = sum(expd[f"# {st.session_state.test_name} Samples"][expd["Train/Test"] == "Test"]) + sum(expd[f"# {st.session_state.control_name} Samples"][expd["Train/Test"] == "Test"])
    len_all = len_train + len_test
    if (len_test) > 0:
        if len_all < 500:
            q3 += 5
        elif len_all < 1000:
            q3 += 10
        elif len_all < 5000:
            q3 += 15
        elif len_all < 10000:
            q3 += 20
        else: 
            q3 += 25
    
    

    q1 = 0
    if len_train > 5000:
        q1 += 25
    elif len_train > 1000:
        q1 += 20
    elif len_train > 500:
        q1 += 15
    elif len_train > 100:
        q1 += 10
    else:
        q1 += 5

    st.session_state.responses[0]["Total Sample Size"] = ([len_all], q3)
    st.session_state.responses[0]["Train \nSample \nSize"] = ([len_train], q1)

    rel_score = 0
    # Relevance Q1
    g1 = sum(expd[f"# {st.session_state.test_name} Samples"]) 
    g2 = sum(expd[f"# {st.session_state.control_name} Samples"])

    if (g1+g2 > 0):
        p = g1/(g1 + g2)

        if p == 0 or p == 1:
            rel_score += 5
        elif p < 0.5:
            rel_score += 15
        else:
            rel_score += 25

    st.session_state.responses[1]["Relevance Experimental Design"] = ([], rel_score)



    
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

    train_ses = hanley_mcneil(train_aucs, expd.loc[expd["Train/Test"] == "Train", f"# {st.session_state.test_name} Samples"].values, expd.loc[expd["Train/Test"] == "Train", f"# {st.session_state.control_name} Samples"].values)
    test_ses = hanley_mcneil(test_aucs, expd.loc[expd["Train/Test"] == "Test", f"# {st.session_state.test_name} Samples"].values, expd.loc[expd["Train/Test"] == "Test", f"# {st.session_state.control_name} Samples"].values)

    feff_train_auc = np.sum(1/(train_ses)**2 * train_aucs) / np.sum(1/(train_ses)**2)
    feff_test_auc = np.sum(1/(test_ses)**2 * test_aucs) / np.sum(1/(test_ses)**2)

    train_chi_sq = np.sum(1/(train_ses)**2 * (train_aucs - feff_train_auc)**2)
    test_chi_sq = np.sum(1/(test_ses)**2 * (test_aucs - feff_test_auc)**2)

    train_p = 1 - stats.chi2.cdf(train_chi_sq, df = len(train_aucs)-1)
    test_p = 1 - stats.chi2.cdf(test_chi_sq, df = len(test_aucs)-1)

    # print(f"P value of variance within train aucs: {train_p}")
    # print(f"P value of variance within test aucs: {test_p}")

    def pooled_auc_and_var(aucs, ses, chi_sq):
        weights = 1.0 / (ses**2)
        k = len(aucs)
        c = np.sum(weights) - np.sum(weights**2) / np.sum(weights)
        tau_sq = max(0, (chi_sq - k + 1) / c)
        weights = 1.0 / (ses**2 + tau_sq)
        pooled = np.sum(weights * aucs) / np.sum(weights)
        var = 1.0 / np.sum(weights)
        return pooled, var
    
    train_wauc, train_wauc_var = pooled_auc_and_var(train_aucs, train_ses, train_chi_sq)
    test_wauc, test_wauc_var = pooled_auc_and_var(test_aucs, test_ses, test_chi_sq)

    se_diff = np.sqrt(train_wauc_var + test_wauc_var)

    perf_drop = max(0, train_wauc-test_wauc)
    perf_drop_z = perf_drop/se_diff

    # print(f"P value of drop between train and test aucs: {perf_drop_z}")


    # Parameters to consider for final score:

    # perf_drop : Drop in performance between train and test
    # perf_drop_z : Significance of the drop
    # tau_sq : Variance between cohorts within either train or test
    # train_chi_sq, train_p : How variable AUC performance is across train cohorts and its significance
    # test_chi_sq, test_p : How variable AUC performance is across test cohorts and its significance


    #Temporary return statement for testing we need to figure out how to weight all these different parameters
    return perf_drop

def score_reproducibility(inputs):
    scores = [4, 1, 1, 2, 6, 10, 6]

    repro_score = 0

    for i in range(len(inputs)):
        if inputs[i]:
            repro_score += scores[i]
    
    return repro_score

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
        "No outcome-linked cohorts": 0,

        "> 3 independent readout types": 20,
        "1-3 independent readout types": 10,
        "Not applicable": 0,

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

        max_width = 115
        max_height = 150
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

        class RotatedParagraph(Flowable):
            def __init__(self, paragraph, angle=90, max_text_width=150):
                super().__init__()
                self.paragraph = paragraph
                self.angle = angle
                # Cap the max width so ReportLab's 72000 test value doesn't explode the cell
                self.max_text_width = max_text_width

            def wrap(self, availWidth, availHeight):
                # Prevent ReportLab's "infinity" measurement from creating a 72000-point wide string
                safe_text_width = min(availHeight, self.max_text_width)
                
                # Calculate paragraph bounds with the clamped width
                w, h = self.paragraph.wrap(safe_text_width, availWidth)
                
                # Swap width and height for the rotation
                self.width = h
                self.height = w
                
                return self.width, self.height

            def draw(self):
                canv = self.canv
                canv.saveState()
                
                if self.angle == 90:
                    canv.translate(self.width, 0)
                    canv.rotate(90)
                elif self.angle == 270:
                    canv.translate(0, self.height)
                    canv.rotate(270)
                    
                self.paragraph.drawOn(canv, 0, 0)
                canv.restoreState()
                canv = self.canv
                canv.saveState()
                
                if self.angle == 90:
                    canv.translate(self.width, 0)
                    canv.rotate(90)
                elif self.angle == 270:
                    canv.translate(0, self.height)
                    canv.rotate(270)
                    
                self.paragraph.drawOn(canv, 0, 0)
                canv.restoreState()

        title = Paragraph(score_name, ParagraphStyle('ScoreTitle', parent=styles['Heading2'], fontSize=16, leading=20, textColor=colors.Color(color[0]/255, color[1]/255, color[2]/255, alpha=color[3]/255), alignment=1, fontName = "Inter-Bold"))
        title = RotatedParagraph(title, angle = 90)

        data = [[[title], image, render_pie(score, color, resp), render_spider(resp, color)]]

        col_widths = [50, 100, 125, 175]



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

    def render_spider(resp, color):
        r, g, b = [x / 255.0 for x in color[:3]]
        alpha = (color[3] / 255.0) if len(color) > 3 else 1.0

        stroke = colors.Color(r, g, b, alpha=alpha)
        fill = colors.Color(r, g, b, alpha = 0.5)

        d = Drawing(200, 150)

        pc = SpiderChart()
        
        pc.x = 50
        pc.y = 25
        pc.width = 100
        pc.height = 100


        pc.data = [
            [x[1] for x in resp.values()]
        ]

        pc.labels = list(resp.keys())
        pc.spokeLabels.fontSize = 7
        pc.spokeLabels.fontName = "Inter-Medium"

        if pc.data == [[]]:
            pc.data = [[0]]

        chart_x, chart_y = 50, 25
        chart_w, chart_h = 100,100

        cx = chart_x + (chart_w / 2)
        cy = chart_y + (chart_h / 2)
        max_radius = min(chart_w, chart_h) / 2

        num_rings = 5
        for i in range(1, num_rings + 1):
            r = max_radius * (i / num_rings)
            d.add(Circle(
                cx, cy, r,
                fillColor=None,
                strokeColor=colors.HexColor("#E0E0E0"),
                strokeWidth=1
            ))

        pc.strands.strokeColor = colors.HexColor("#CCCCCC")
        pc.strands.strokeWidth = 1
        pc.strands.strokeWidth = 1
        pc.strands.strokeWidth = 1.5
        pc.strands[0].strokeColor = stroke
        pc.strands[0].fillColor = fill
        for i in range(len(pc.labels)):
            angle = math.pi/2 - 2 * math.pi * (i/len(pc.labels))
            num_n = pc.labels[i].count("\n") + 1
            pc.spokeLabels[i].dy = 15 * math.atan(num_n) ** 2 * math.sin(angle)
            pc.spokeLabels[i].dx = 15 * math.atan(num_n) ** 2 * math.cos(angle)

        d.add(pc)

        return d

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
    story.append(render_metric("human.png", (30, 75, 150, 255), h_score, h_resp, "HUMANNESS", "Measures how strongly a discovery or model is anchored in real human biology."))
    story.append(render_metric("relevance.png", (80, 120, 60, 255), r_score, r_resp, "RELEVANCE", "Measures how closely a model connects to clinically meaningful disease states, outcomes, and treatment responses."))
    story.append(render_metric("nam.png", (200, 150, 60, 255), n_score, n_resp, "NAM FIDELITY", "Measures how faithfully and reproducibly a NAM captures human disease biology in a scalable, fit-for-purpose manner."))

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
    st.markdown("### Control & Experimental Conditions")
    st.text_input(label = "Control group name", value = "Control", key = "control_name")
    st.text_input(label = "Test group name", value = "Test", key = "test_name")
    st.markdown("### Cohort Breakdown")
    st.session_state.expd.columns = ["Cohort #", f"# {st.session_state.test_name} Samples", f"# {st.session_state.control_name} Samples", "Train/Test"]
    st.dataframe(st.session_state.expd)

    with st.container(border=True):
        g1 = st.number_input(f"# {st.session_state.test_name} Samples", min_value = 0)
        g2 = st.number_input(f"# {st.session_state.control_name} Samples", min_value = 0)
        t = st.selectbox(label="Train/Test", options = ["Train", "Test"])
        if st.button("+ Add Cohort", type = "primary"):
            expd = st.session_state.expd
            st.session_state.expd.loc[len(expd)] = {"Cohort #": len(expd)+1, f"# {st.session_state.test_name} Samples": g1, f"# {st.session_state.control_name} Samples": g2, "Train/Test": t}

            # cohort_numbers(st.session_state.expd)
            st.rerun()    
    score_expd(st.session_state.expd)

with hum:
    expd = st.session_state.expd
    h_questions = Questionnaire([Question("Human\nAnchored", ["Was the original ML model built from human tissues or body fluids (blood, BAL, etc.)?"], [lambda **kw: st.selectbox(label = "", options = ("Yes", "No"), **kw)], lambda x: 5 if x[0] == "Yes" else 0, definitions=[Definition("BAL", "Bronchoalveolar lavage (BAL): Fluid collected from the lower airways during bronchoscopy. BAL contains immune cells, proteins, microbes, and soluble biomarkers that directly reflect lung biology.", "label", True)]),
                   Question("Data Quality", ["What was the quality of the dataset(s) used to build the model?"], [lambda **kw: st.selectbox(label = "", options = ("High quality (Deep sequencing, > 50M reads/sample, validated platforms)", "Not high quality < 50M reads/sample or not validated"), **kw)], lambda x: 10 if "> 50M" in x[0] else (5 if "< 50M" in x[0] else 0)),
                   Question("Cross Species \nConservation", ["Is the entity conserved across species? (foundational biology but not a substitute for humanness)"], [lambda **kw: st.selectbox(label = "", options = ("Yes", "No"), **kw)], lambda x: 10 if x[0] == "Yes" else 0, definitions = [Definition("species", "Species: A biological organism (e.g., human, mouse, rat, non-human primate) used to generate or validate findings. Human-derived evidence contributes to Humanness; cross-species conservation provides supportive, but not primary, evidence.", "label", True)]),
                   Question("ROC\nAUC", [f"AUC of Cohort #{x+1} ({expd.iloc[x]["Train/Test"]} n = {int(expd.loc[expd["Cohort #"] == x+1][f"# {st.session_state.test_name} Samples"].iloc[0])+int(expd.loc[expd["Cohort #"] == x+1][f"# {st.session_state.control_name} Samples"].iloc[0])})" for x in range(len(expd))], [lambda x=x, **kw: st.number_input(f"AUC of Cohort #{x+1} ({expd.iloc[x]["Train/Test"]} n = {int(expd.loc[expd["Cohort #"] == x+1][f"# {st.session_state.test_name} Samples"].iloc[0])+int(expd.loc[expd["Cohort #"] == x+1][f"# {st.session_state.control_name} Samples"].iloc[0])})", max_value= 1.0, format = "%.4f") for x in range(len(expd))], score_aucs)], 
                   
                   0)

with rel:
    expd = st.session_state.expd
    r_questions = Questionnaire([Question("Disease\nSeverity", ["Was the model originally built or independently validated to classify disease severity, progression, therapeutic response, relapse, survival, or clinical outcomes?"], [lambda **kw: st.selectbox(label = "", options = ("Yes, prospectively validated", "Yes, retrospectively validated", "Exploratory association only", "No outcome association"), **kw)], score, definitions=[Definition("disease severity", "Disease severity: The extent or stage of illness (e.g., mild, moderate, severe, progressive, remission, relapse). Models linked to disease severity are expected to better capture clinically meaningful biology.", "label", True), Definition("clinical outcomes", "Clinical outcomes: Patient-centered endpoints such as disease-free, transplant-free or overall survival, disease progression (complications, by symptoms or radiologic or other clinically accepted scores), relapse, treatment response, symptom improvement, hospitalization or mortality in hospital, or adverse events that determine clinical benefit typically in Phase 3 trials looking for efficacy.", "label", True)]),
                   Question("Prospective Cohorts", ["Were datasets prospectively collected with future outcomes annotated after tissue diversion?"], [lambda **kw: st.selectbox(label = "", options = (">5 cohorts","3-5 cohorts","1-2 cohorts","Retrospective only","No outcome-linked cohorts"), **kw)], score, definitions = [Definition("tissue diversion", "Tissue diversion: The time at which a human specimen is collected from clinical care or surgery for research. Prospective outcome studies link future clinical events to samples obtained at the time of tissue diversion.", "label", True)]),
                   Question("GWAS\nSupport", ["Is there additional support from GWAS and/or other biological support?"], [lambda **kw: st.selectbox(label = "", options = ("Yes", "No"), **kw)], lambda x: 25 if x[0] == "Yes" else 0, definitions=[Definition("GWAS", "Genome-Wide Association Study (GWAS): A study that identifies genetic variants associated with human traits or disease. Within TRUST-NAM, GWAS is one example of human biological support, alongside rare variants, eQTLs, CRISPR, drug-target evidence, and other causal data.", "label", True)])],
                   
                   1)

with nam:
    expd = st.session_state.expd
    n_questions = Questionnaire([Question("Signature Capture (AUC)", ["What is the AUC ROC in healthy vs disease classification?"], [lambda **kw: st.number_input(label = "", min_value = 0.0, max_value = 1.0, format = "%.4f", **kw)], lambda x: 20 if x[0] >= 0.85 else (10 if x[0] >= 0.7 else 0)),
                                 Question("Perturbation\nAlignment", ["Alignment of perturbation response between the NAM and human disease biology (multi-omic + phenotype)"], [lambda **kw: st.selectbox(label = "", options = ("> 3 independent readout types", "1-3 independent readout types", "Not applicable"), **kw)], score, definitions = [Definition("perturbation", "Perturbation: An intentional experimental intervention (drug, gene editing, cytokine, infection, environmental stimulus, etc.) used to test whether a NAM responds as predicted from human biology.", "label", True)]),
                                 Question("Outcome\nPrediction", ["What is the AUC of post-perturbation signature prediction of prospective human outcomes?"], [lambda **kw: st.number_input(label = "", min_value=0.0, max_value=1.0, format="%.4f", **kw)], lambda x: 20 if x[0] >= 0.85 else (10 if x[0] >= 0.7 else 0), definitions = [Definition("perturbation", "Perturbation: An intentional experimental intervention (drug, gene editing, cytokine, infection, environmental stimulus, etc.) used to test whether a NAM responds as predicted from human biology.", "label", True)]),
                                 Question("Animal Model\nCorroboration", ["Signature capture of human disease biology in animal models (AUC)", "Predicts functional/phenotypic outcomes post-perturbation in prospective cohorts (AUC)", "Post-perturbation signature matches model signature (correlation)", "Post-perturbation signature predicts outcomes in human cohorts (AUC)"], [lambda **kw: st.number_input(label = "", min_value=0.0, max_value=1.0, format="%.4f", **kw), lambda **kw: st.number_input(label = "", min_value=0.0, max_value=1.0, format="%.4f", **kw), lambda **kw: st.number_input(label = "", min_value=-1.0, max_value=1.0, format="%.4f", **kw), lambda **kw: st.number_input(label = "", min_value=0.0, max_value=1.0, format="%.4f", **kw)], lambda x: 10 if (y := int(x[0] >=0.75) + int(x[1] >= 0.6) + int(x[2] >= 0.7) + int(x[3] >= 0.6)) == 4 else (5 if y == 3 else (5 if y == 2 else (0 if y == 1 else 0))), definitions = [Definition("perturbation", "Perturbation: An intentional experimental intervention (drug, gene editing, cytokine, infection, environmental stimulus, etc.) used to test whether a NAM responds as predicted from human biology.", "label", True)]),
                                 Question("Reproducibility/\nAdoption", ["Simplicity - Minimal components; easy to implement; low technical complexity", "Scalability - High-throughput; cost-effective; readily accessible", "Least Perturbed Design - Physiologically relevant; minimal exogenous manipulation", "Defined Context of Use - Clear indications, limitations, and intended use", "Standardized SOPs - SOPs available, validated, and widely adopted", "Biological & Technical replicates - Adequate biological replicates (unique donors); technical replicates; statistically powered", "Fit-for-Purpose Benchmarking - Benchmarked against appropriate state-of-the-art standards"], [lambda **kw: st.toggle(label = "", **kw),lambda **kw: st.toggle(label = "", **kw),lambda **kw: st.toggle(label = "", **kw),lambda **kw: st.toggle(label = "", **kw),lambda **kw: st.toggle(label = "", **kw),lambda **kw: st.toggle(label = "", **kw),lambda **kw: st.toggle(label = "", **kw)], score_reproducibility)
                                 ],
                                
                                2)

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
    