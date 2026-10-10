"""Generate demo_hinglish.csv with planted rating rule."""
import pandas as pd
import random
import hashlib


def generate_demo_data(output_path='data/demo_hinglish.csv', num_reviews=300):
    """
    Generate 300 reviews with planted rating rule:
    base 4.4, minus 1.2 battery, minus 0.8 delivery, minus 0.5 packaging, plus noise.
    """
    random.seed(42)

    reviews = []

    # Aspects and phrasings
    battery_positive = [
        'battery backup is amazing',
        'battery lasts all day',
        'great battery life',
        'battery kamaal hai',
        'battery bahut acha hai',
        'battery backup zabardast',
    ]
    battery_negative = [
        'battery dies quickly',
        'battery backup is poor',
        'battery drains fast',
        'battery kharab hai',
        'battery bekaar hai',
        'battery ghatiya hai',
    ]

    delivery_positive = [
        'delivery was fast',
        'delivery on time',
        'packaging was good',
        'delivery bahut acha',
    ]
    delivery_negative = [
        'delivery took too long',
        'delivery was late',
        'packaging was damaged',
        'delivery bekaar tha',
        'package aaya damaged',
    ]

    packaging_positive = [
        'packaging is nice',
        'unboxing experience great',
        'package quality good',
    ]
    packaging_negative = [
        'packaging is poor',
        'package came damaged',
        'packaging bekaar',
    ]

    camera_positive = [
        'camera quality is excellent',
        'photos are sharp',
        'camera is amazing',
        'camera bahut acha',
    ]
    camera_negative = [
        'camera quality is bad',
        'photos are blurry',
        'camera sucks',
        'camera kharab hai',
    ]

    performance_positive = [
        'phone is very fast',
        'no lag at all',
        'performance is smooth',
        'performance zabardast',
    ]
    performance_negative = [
        'phone lags a lot',
        'performance is slow',
        'phone freezes',
        'lag bahut ho raha',
    ]

    # Generate reviews
    for i in range(num_reviews):
        # Decide which aspects are mentioned
        has_battery = random.random() < 0.7
        has_delivery = random.random() < 0.6
        has_packaging = random.random() < 0.5
        has_camera = random.random() < 0.6
        has_performance = random.random() < 0.5

        # Decide sentiment per aspect
        battery_neg = has_battery and random.random() < 0.4
        delivery_neg = has_delivery and random.random() < 0.3
        packaging_neg = has_packaging and random.random() < 0.3
        camera_neg = has_camera and random.random() < 0.3
        performance_neg = has_performance and random.random() < 0.4

        # Build review text
        clauses = []
        if has_battery:
            clauses.append(random.choice(battery_negative if battery_neg else battery_positive))
        if has_delivery:
            clauses.append(random.choice(delivery_negative if delivery_neg else delivery_positive))
        if has_packaging:
            clauses.append(random.choice(packaging_negative if packaging_neg else packaging_positive))
        if has_camera:
            clauses.append(random.choice(camera_negative if camera_neg else camera_positive))
        if has_performance:
            clauses.append(random.choice(performance_negative if performance_neg else performance_positive))

        review_text = '. '.join(clauses)

        # Apply planted rating rule: base 4.4, minus 1.2 battery, minus 0.8 delivery, minus 0.5 packaging
        rating = 4.4
        if battery_neg:
            rating -= 1.2
        if delivery_neg:
            rating -= 0.8
        if packaging_neg:
            rating -= 0.5

        # Add noise
        rating += random.gauss(0, 0.3)

        # Clip to 1-5
        rating = max(1, min(5, rating))
        rating = round(rating)

        # Add sarcasm cases (5 total)
        if i < 5:
            if i == 0:
                review_text = "Great phone, broke after one day! Amazing experience."
                rating = 1
            elif i == 1:
                review_text = "Wow, battery dies in 2 hours. Fantastic!"
                rating = 1
            elif i == 2:
                review_text = "Thanks for the terrible delivery. Really appreciate it."
                rating = 2
            elif i == 3:
                review_text = "Excellent camera, unfortunately it overheats constantly."
                rating = 2
            elif i == 4:
                review_text = "Love how the phone lags every 5 minutes!"
                rating = 2

        # Add safety cases (3 total)
        if i >= 5 and i < 8:
            if i == 5:
                review_text = "Phone caught fire after charging overnight. Do not buy!"
                rating = 1
            elif i == 6:
                review_text = "Battery started smoking, very dangerous. Phone is a fire hazard."
                rating = 1
            elif i == 7:
                review_text = "Got electric shock from the charger. This is not safe!"
                rating = 1

        # Add mixed-opinion reviews (10 total)
        if i >= 8 and i < 18:
            review_text = "Camera is excellent but battery backup is terrible. Overall disappointed."
            rating = 2 if i % 2 == 0 else 3

        # Determine version (v1 or v2, v2 has better delivery)
        version = 'v2' if i % 2 == 0 else 'v1'
        if version == 'v2' and delivery_neg:
            # v2 fixes delivery
            review_text = review_text.replace('delivery was late', 'delivery was on time')
            review_text = review_text.replace('delivery took too long', 'delivery was fast')
            rating += 0.8

        reviews.append({
            'review_id': f"review_{i}",
            'review_text': review_text,
            'rating': rating,
            'version': version,
            'date': '2024-01-01'
        })

    df = pd.DataFrame(reviews)
    df.to_csv(output_path, index=False)
    print(f"Generated {len(df)} demo reviews to {output_path}")
    print(f"Average rating: {df['rating'].mean():.2f}")
    print(f"Negative reviews (rating <= 2): {(df['rating'] <= 2).sum()}")
    return df


if __name__ == '__main__':
    generate_demo_data()
