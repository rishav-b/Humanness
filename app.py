import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import chi2_contingency

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
st.text("Text about CHC text about CHC")

expd, hum, rel, nam = st.tabs(["Experimental Design", "Humanness", "Relevance", "NAM Fidelity"])

def cohort_numbers(expd):
    """
    Computes variation among the cohorts in their composition
    """
    
    train_data = np.array([[expd["# Positive Samples"].iloc[x], expd["# Negative Samples"].iloc[x]] for x in range(len(expd)) if expd["Train/Test"].iloc[x] == "Train"])
    test_data = np.array([[expd["# Positive Samples"].iloc[x], expd["# Negative Samples"].iloc[x]] for x in range(len(expd)) if expd["Train/Test"].iloc[x] == "Test"])
    
    v = []

    for data in [train_data, test_data]:

        chi2, p_val, dof, expected = chi2_contingency(data)
        #Cramer's v
        v.append(np.sqrt(chi2/(data.sum() * min(data.shape[0]-1, data.shape[1]-1))))
    
    #Not sure what to do with these yet
    
with expd:
    st.dataframe(st.session_state.expd)

    with st.container(border=True):
        g1 = st.number_input("# Positive Samples", min_value = 0)
        g2 = st.number_input("# Negative Samples", min_value = 0)
        t = st.selectbox(label="Train/Test", options = ["Train", "Test"])
        if st.button("+ Add Cohort", type = "primary"):
            expd = st.session_state.expd
            st.session_state.expd.loc[len(expd)] = {"Cohort #": len(expd)+1, "# Positive Samples": g1, "# Negative Samples": g2, "Train/Test": t}

            cohort_numbers(st.session_state.expd)
            st.rerun()


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
    """,
    unsafe_allow_html=True
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
                .st-key-slide_box_{self.page} {{
                    background-color: #f9f9f9;
                    padding: 20px;
                    border-radius: 8px;
                }}
                @keyframes slideIn {{
                    0% {{
                        opacity: 0;
                        transform: translateX(300px);
                    }}
                    100% {{
                        opacity: 1;
                        transform: translateX(0px);
                    }}
                }}
            .st-key-slide_box_{self.page} {{
                animation: {'slideIn 0.4s ease-out forwards' if st.session_state.animate_slide else 'none'} !important;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )

        st.button(":material/arrow_forward:", key=f"next_btn_{self.page}_{st.session_state.cq[self.page]}",
            on_click=self.advance, disabled = st.session_state.cq[self.page] == self.num_questions
        )

        with st.container(key = f"slide_box_{self.page}", border=True):
            self.inputs = [r() for r in self.input_renderers]

        st.session_state.animate_slide = False
    
    def advance(self):
        st.session_state.animate_slide = True
        st.session_state.cq[self.page] = min(st.session_state.cq[self.page] + 1, self.num_questions-1)
        st.session_state.responses[self.page][self.question_id] = self.inputs
        self.get_score()

class Questionnaire:
    def __init__(self, questions: list[Question], page):
        self.questions = questions
        self.page = page

        for q in self.questions:
            q.num_questions = len(self.questions)
            q.page = self.page
        
        self.questions[st.session_state.cq[self.page]].render_question()



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

    train_weights = 1.0 / (train_ses**2)
    train_wauc = np.sum(train_weights * train_aucs) / np.sum(train_weights)

    test_weights = 1.0 / (test_ses**2)
    feff_test_auc = np.sum(test_weights * test_aucs) / np.sum(test_weights)
    
    train_chi_sq = np.sum(train_weights * (train_aucs - train_wauc)**2)
    test_chi_sq = np.sum(test_weights * (test_aucs - feff_test_auc)**2)

    test_q = np.sum(test_weights*(test_aucs - feff_test_auc)**2)
    test_c = np.sum(test_weights) - np.sum(test_weights**2) / np.sum(test_weights)

    test_tau_sq = max(0, (test_q-len(test_aucs)+1)/test_c)

    test_random_weights = 1/(test_ses**2 + test_tau_sq)

    reff_test_auc = np.sum(test_random_weights * test_aucs) / np.sum(test_random_weights)

    train_wauc_var = 1/np.sum(train_weights)
    reff_test_var = 1/np.sum(test_random_weights)

    se_diff = np.sqrt(train_wauc_var + reff_test_var)

    perf_drop = max(0, train_wauc-reff_test_auc)
    perf_drop_z = perf_drop/se_diff



    # Parameters to consider for final score:

    # perf_drop : Drop in performance between train and test
    # perf_drop_z : Significance of the drop
    # tau_sq : Variance between cohorts

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
    

with hum:
    expd = st.session_state.expd
    h_questions = Questionnaire([Question("human_anchored", [lambda: st.selectbox("Was the original ML model built from human tissues or body fluids (blood, BAL, etc.)?", options = ("Yes", "No"))], lambda x: 5 if x == "Yes" else 0),
                   Question("data_quality", [lambda: st.selectbox("What was the quality of the dataset(s) used to build the model?", options = ("High quality (Deep sequencing, > 50M reads/sample, validated platforms)", "Not high quality < 50M reads/sample or not validated"))], lambda x: 10 if "> 50M" in x else 0),
                   Question("cross_species_conservation", [lambda: st.selectbox("Is the entity conserved across species? (foundational biology but not a substitute for humanness)", options = ("Yes", "No"))], lambda x: 5 if x == "Yes" else 0),
                   Question("roc_auc", [lambda x=x: st.number_input(f"AUC of Cohort #{x+1} ({expd.iloc[x]["Train/Test"]} n = {int(expd.loc[expd["Cohort #"] == x+1]["# Positive Samples"].iloc[0])+int(expd.loc[expd["Cohort #"] == x+1]["# Negative Samples"].iloc[0])})", max_value= 1.0, key = str(x), format = "%.4f") for x in range(len(expd))], score_aucs)], 
                   
                   0)

with rel:
    expd = st.session_state.expd
    r_questions = Questionnaire([Question("disease_severity", [lambda: st.selectbox("Was the model originally built or independently validated to classify disease severity, progression, therapeutic response, relapse, survival, or clinical outcomes?", options = ("Yes, prospectively validated", "Yes, retrospectively validated", "Exploratory association only", "No outcome association"))], score),
                   Question("prospective_cohorts", [lambda: st.selectbox("Were datasets prospectively collected with future outcomes annotated after tissue diversion?", options = (">5 cohorts","3-5 cohorts","1-2 cohorts","Retrospective only","No outcome-linked cohorts"))], score),
                   Question("gwas", [lambda: st.selectbox("Is there additional support from GWAS and/or other biological support?", options = ("Yes", "No"))], lambda x: 25 if x == "Yes" else 0)],
                   
                   1)
    