"""Arabic/Egyptian readiness, story traceability and the tested-sample button."""
from app import carry, interviews
from app.agents.builder import MvpSpec, UserStory
from app.agents.interview_analyst import Evidence, InterviewAnalysis
from app.arabic import is_polite_non_commitment, normalize_ar
from app.mvp_app import render_mvp_page


def _analysis(evidence, confirmed=True):
    return InterviewAnalysis(language="Egyptian Arabic", problem_confirmed=confirmed, why="w", current_workaround="ChatGPT",
                             cost_of_problem="3 ساعات", commitment="none", evidence=evidence, surprise="none", ask_next_time=["q"])


def test_arabic_spelling_variants_do_not_drop_real_quotes():
    transcript = "انا بقعد تلات ساعات أكتب الملخصات قبل الامتحان، وبجد المذاكرة متعبة."
    quote = "انا بقعد تلات ساعات اكتب الملخصات قبل الامتحان"  # Whisper wrote أكتب, the analyst wrote اكتب
    a, dropped = interviews.verify(_analysis([Evidence(quote=quote, shows="pain")]), transcript)
    assert a.evidence and not dropped and a.problem_confirmed
    assert normalize_ar("مذاكرةٌ إلى") == "مذاكره الي"


def test_polite_egyptian_non_commitments_are_red_flags_not_evidence():
    t = "الفكرة جامدة جداً إن شاء الله هجربه أكيد لما ينزل"
    a, _ = interviews.verify(_analysis([Evidence(quote="إن شاء الله هجربه أكيد", shows="intent")]), t)
    assert not a.evidence and a.red_flags and not a.problem_confirmed
    for q in ("ربنا يسهل", "فكرة جامدة جداً", "I would totally use it", "insha'allah"):
        assert is_polite_non_commitment(q), q
    assert not is_polite_non_commitment("دفعت 200 جنيه لمدرس خصوصي الشهر اللي فات")


def test_stories_cite_only_verified_quote_ids():
    class St:
        interviews = [{"analysis": {"evidence": [{"quote": "I rewrite notes for 3 hours"}]}}]
    q = carry.quote_ids(St())
    assert q == {"IV1-Q1": "I rewrite notes for 3 hours"}
    s = MvpSpec.model_construct(user_stories=[UserStory(id="US1", as_a="a", i_want="b", so_that="c", acceptance=["x"], evidence="IV1-Q1"),
                                              UserStory(id="US2", as_a="a", i_want="b", so_that="c", acceptance=["x"], evidence="IV9-Q9")])
    out = carry.trace_stories(s, q)
    assert [u.evidence for u in out.user_stories] == ["IV1-Q1", "ASSUMPTION-DRIVEN"]


def test_mvp_page_offers_the_tested_sample_in_one_click():
    page, _ = render_mvp_page(run_id="r1", product_name="P", one_line="o", story={}, funcs=[("summarize", ["text"])],
                              checks_passed="3/3", sample='Lecture 1: "cells" & <tissues>')
    assert "Load tested sample input" in page and 'name="text" value="Lecture 1: &quot;cells&quot; &amp; &lt;tissues&gt;"' in page
    assert "<script" not in page
