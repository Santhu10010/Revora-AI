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
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unable to load supporting reviews');
      } finally {
        setLoading(false);
      }
    };

    fetchReviews();
  }, [analysisId, aspect, polarity]);

  if (loading) {
    return (
      <div className="enterprise-card mx-auto max-w-4xl p-8">
        <p className="text-[#737686]">Loading reviews...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="enterprise-card mx-auto max-w-4xl p-8">
        <p className="text-red-600">Error: {error}</p>
        <button
          onClick={onBack}
          className="mt-4 rounded bg-[#004ac6] px-4 py-2 text-sm font-medium text-white"
        >
          Back
        </button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl">
      <button
        onClick={onBack}
        className="mb-5 rounded border border-[#e0e3e5] bg-[#f2f4f6] px-3 py-2 text-sm font-medium text-[#515f74] hover:bg-[#e6e8ea]"
      >
        ← Back to prioritization
      </button>

      <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.16em] text-[#737686]">Evidence review</p>
      <h2 className="mb-2 text-2xl font-semibold tracking-tight">
        {aspect} - {polarity === 'neg' ? 'Negative' : 'Positive'} Reviews
      </h2>
      <p className="mb-6 text-sm text-[#737686]">{reviews.length} reviews found · Supporting evidence</p>

      <div className="space-y-4">
        {reviews.length === 0 && <div className="enterprise-card p-6 text-sm text-[#737686]">No supporting reviews found.</div>}
        {reviews.map((review) => (
          <div key={review.review_id} className="enterprise-card border-l-4 border-l-[#004ac6] p-5">
            <div className="flex justify-between items-start mb-3">
              <div>
                <p className="font-mono text-xs text-[#737686]">{review.review_id}</p>
                <div className="flex gap-2 mt-1">
                  <span                   className="inline-block rounded bg-[#f2f4f6] px-2 py-1 text-xs text-[#515f74]">
                    {review.lang}
                  </span>
                  {review.rating && (
                    <span                     className="inline-block rounded bg-[#dbe1ff] px-2 py-1 text-xs text-[#003ea8]">
                      Rating: {review.rating}/5
                    </span>
                  )}
                </div>
              </div>
            </div>

            <p className="leading-relaxed text-[#191c1e]">
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
