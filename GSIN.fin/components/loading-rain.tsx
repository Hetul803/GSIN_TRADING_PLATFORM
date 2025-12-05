'use client';

import { useEffect, useState } from 'react';

interface RainDrop {
  id: number;
  left: number;
  delay: number;
  duration: number;
}

export function LoadingRain() {
  const [drops, setDrops] = useState<RainDrop[]>([]);

  useEffect(() => {
    // Generate rain drops
    const newDrops: RainDrop[] = [];
    for (let i = 0; i < 50; i++) {
      newDrops.push({
        id: i,
        left: Math.random() * 100,
        delay: Math.random() * 2,
        duration: 0.5 + Math.random() * 0.5,
      });
    }
    setDrops(newDrops);
  }, []);

  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none z-50">
      {drops.map((drop) => (
        <div
          key={drop.id}
          className="absolute top-0 w-0.5 h-8 bg-gradient-to-b from-blue-400 to-transparent opacity-60"
          style={{
            left: `${drop.left}%`,
            animation: `rain ${drop.duration}s linear ${drop.delay}s infinite`,
          }}
        />
      ))}
      <style jsx>{`
        @keyframes rain {
          0% {
            transform: translateY(-100vh);
            opacity: 0;
          }
          10% {
            opacity: 0.6;
          }
          90% {
            opacity: 0.6;
          }
          100% {
            transform: translateY(100vh);
            opacity: 0;
          }
        }
      `}</style>
    </div>
  );
}

