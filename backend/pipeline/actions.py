"""Action generation: tickets and replies."""

def generate_ticket(insight, df):
    """Generate a ticket from an insight."""
    return {
        'title': f"Fix {insight.aspect} issues",
        'team': 'Product',
        'priority': 'P2',
        'summary': f"{insight.mentions} mentions, {insight.pct_negative:.1%} negative",
        'evidence': [],
        'impact': f"Estimated +{insight.damage:.1f} rating points"
    }


def generate_reply(insight):
    """Generate a reply draft."""
    return f"Thank you for your feedback on {insight.aspect}. We're working to improve this."
