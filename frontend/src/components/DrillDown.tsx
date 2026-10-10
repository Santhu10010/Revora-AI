import React, { useEffect, useState } from 'react';
import { api, Review } from '../lib/api';

interface DrillDownProps {
  analysisId: string;
  aspect: string;
  polarity: string;
  onBack: () => void;
}

export const DrillDown: React.FC<DrillDownProps> = ({ analysisId, aspect, polarity, onBack }) => {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchReviews = async () => {
      try {
        const data = await api.getReviews(analysisId, aspect, polarity);
        setReviews(data.reviews);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchReviews();
  }, [analysisId, aspect, polarity]);

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto p-8">
        <p className="text-gray-600">Loading reviews...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto p-8">
        <p className="text-red-600">Error: {error}</p>
        <button
          onClick={onBack}
          className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md"
        >
          Back
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <button
        onClick={onBack}
        className="mb-6 px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300"
      >
        ← Back
      </button>

      <h2 className="text-2xl font-bold mb-2">
        {aspect} - {polarity === 'neg' ? 'Negative' : 'Positive'} Reviews
      </h2>
      <p className="text-gray-600 mb-6">{reviews.length} reviews found</p>

      <div className="space-y-4">
        {reviews.map((review) => (
          <div key={review.review_id} className="bg-white rounded-lg shadow p-6 border-l-4 border-blue-400">
            <div className="flex justify-between items-start mb-3">
              <div>
                <p className="text-sm text-gray-500">{review.review_id}</p>
                <div className="flex gap-2 mt-1">
                  <span className="inline-block px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded">
                    {review.lang}
                  </span>
                  {review.rating && (
                    <span className="inline-block px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded">
                      Rating: {review.rating}/5
                    </span>
                  )}
                </div>
              </div>
            </div>

            <p className="text-gray-800 leading-relaxed">
              <HighlightedText text={review.text} highlights={review.highlights} />
            </p>
          </div>
        ))}
      </div>
    </div>
  );
};

interface HighlightedTextProps {
  text: string;
  highlights: Array<{
    start: number;
    end: number;
    aspect: string | null;
    polarity: string;
    score: number;
  }>;
}

const HighlightedText: React.FC<HighlightedTextProps> = ({ text, highlights }) => {
  if (highlights.length === 0) {
    return <>{text}</>;
  }

  // Sort highlights by start position
  const sorted = [...highlights].sort((a, b) => a.start - b.start);

  const parts = [];
  let lastEnd = 0;

  for (const hl of sorted) {
    if (hl.start > lastEnd) {
      parts.push(
        <span key={`text-${lastEnd}`}>
          {text.substring(lastEnd, hl.start)}
        </span>
      );
    }

    const bgColor = hl.polarity === 'neg' ? 'bg-red-200' : 'bg-green-200';
    parts.push(
      <span
        key={`hl-${hl.start}`}
        className={`highlight ${bgColor} font-semibold`}
        title={`${hl.aspect} (${hl.polarity})`}
      >
        {text.substring(hl.start, hl.end)}
      </span>
    );

    lastEnd = hl.end;
  }

  if (lastEnd < text.length) {
    parts.push(
      <span key={`text-${lastEnd}`}>
        {text.substring(lastEnd)}
      </span>
    );
  }

  return <>{parts}</>;
};
