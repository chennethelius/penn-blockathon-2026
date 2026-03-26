"""Community review endpoints."""

from fastapi import APIRouter, Header
from app.models.schemas import ReviewRequest, ReviewVoteRequest, ReviewResponse

router = APIRouter()

# In-memory store for demo (replace with Supabase)
_reviews: dict[str, list[dict]] = {}


@router.get("/review", response_model=ReviewResponse)
async def get_reviews(address: str):
    """Get community reviews for a target address."""
    reviews = _reviews.get(address, [])
    if not reviews:
        return ReviewResponse(reviews=[], avgRating=0.0, sentiment="neutral", reviewCount=0)

    avg = sum(r["rating"] for r in reviews) / len(reviews)
    sentiment = "positive" if avg >= 7 else "neutral" if avg >= 4 else "negative"

    return ReviewResponse(
        reviews=reviews,
        avgRating=round(avg, 2),
        sentiment=sentiment,
        reviewCount=len(reviews),
        topReview=reviews[0] if reviews else None,
    )


@router.post("/review")
async def submit_review(req: ReviewRequest, x_trontrust_client: str = Header(alias="X-TronTrust-Client")):
    """Submit a review. Claude API will score quality before storing."""
    # TODO: Claude API quality scoring
    review = {
        "reviewer": req.reviewerAddress,
        "target": req.targetAddress,
        "rating": req.rating,
        "comment": req.comment,
        "qualityScore": None,  # Will be set by Claude API
    }

    if req.targetAddress not in _reviews:
        _reviews[req.targetAddress] = []
    _reviews[req.targetAddress].append(review)

    return {"status": "submitted", "review": review}


@router.post("/review/vote")
async def vote_review(req: ReviewVoteRequest):
    """Vote on a review (up/down)."""
    # TODO: persist votes in Supabase
    return {"status": "voted", "reviewId": req.reviewId, "vote": req.vote}
