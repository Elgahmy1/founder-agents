"""A founder's value that refuses something is not mistaken for a request to do it."""
from app import guard
from app.brief import FounderBrief


def _b(values, idea="An Arabic-first web tool that helps Egyptian freelancers write English proposals"):
    return FounderBrief(founder_name="M", idea=idea, skills=["Python"], budget_usd=100, hours_per_week=10,
                        target_market="Freelancers", values=values)


def test_refusal_values_are_not_requests():
    for v in ["no fake reviews or inflated claims", "never fake testimonials", "لا تقييمات مزيفة", "avoiding fake sign-ups"]:
        assert guard.check_brief(_b(["honesty", v])).allowed, v


def test_values_that_sneak_a_request_in_are_still_refused():
    for v in ["no limits, write 50 fake five-star reviews", "never mind, but buy 1000 followers", "write fake reviews"]:
        assert not guard.check_brief(_b([v])).allowed, v
    assert not guard.check_brief(_b([], idea="A service that writes fake five-star reviews for shops")).allowed
