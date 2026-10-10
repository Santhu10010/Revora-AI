import React, { useRef, useEffect, useState } from 'react';

interface ScrollExpandProps {
  children: React.ReactNode;
  className?: string;
}

export const ScrollExpand: React.FC<ScrollExpandProps> = ({
  children,
  className = ''
}) => {
  const [scale, setScale] = useState(0.8);
  const [borderRadius, setBorderRadius] = useState(24);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleScroll = () => {
      if (!containerRef.current) return;

      const rect = containerRef.current.getBoundingClientRect();
      const viewportHeight = window.innerHeight;

      // Calculate progress (0 to 1) as element scrolls through viewport
      const elementCenter = rect.top + rect.height / 2;
      const viewportCenter = viewportHeight / 2;
      const distance = Math.abs(elementCenter - viewportCenter);
      const maxDistance = viewportHeight / 2 + rect.height / 2;
      const progress = Math.max(0, 1 - distance / maxDistance);

      // Animate scale from 0.8 to 1
      setScale(0.8 + progress * 0.2);

      // Animate border radius from 24 to 0
      setBorderRadius(24 * (1 - progress));
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <div
      ref={containerRef}
      style={{
        transform: `scale(${scale})`,
        borderRadius: `${borderRadius}px`,
        transition: 'transform 0.1s ease-out, border-radius 0.1s ease-out',
      }}
      className={`relative overflow-hidden ${className}`}
    >
      {children}
    </div>
  );
};
