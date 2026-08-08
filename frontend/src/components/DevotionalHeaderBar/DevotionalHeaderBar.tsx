export function DevotionalHeaderBar() {
  return (
    <div className="w-full bg-gradient-to-r from-amber-950 via-red-950 to-amber-950 border-b border-amber-500/30 py-1.5 overflow-hidden whitespace-nowrap select-none shadow-md z-30">
      <div className="animate-marquee hover:pause flex items-center font-bold text-xs text-amber-200 tracking-wide">
        <span className="mx-6 text-amber-300 drop-shadow-[0_0_8px_rgba(245,158,11,0.5)]">ॐ श्रीं गणेशाय नमः ।</span>
        <span className="text-amber-500 font-extrabold">•</span>
        <span className="mx-6 text-amber-300 drop-shadow-[0_0_8px_rgba(245,158,11,0.5)]">ॐ श्रीं महालक्ष्म्यै नमः ।</span>
        <span className="text-amber-500 font-extrabold">•</span>
        <span className="mx-6 text-amber-300 drop-shadow-[0_0_8px_rgba(245,158,11,0.5)]">विघ्न विनाशाय, धन-समृद्धि प्रदाय नमः ।</span>
        <span className="text-amber-500 font-extrabold">•</span>

        {/* Duplicate copy for seamless looping */}
        <span className="mx-6 text-amber-300 drop-shadow-[0_0_8px_rgba(245,158,11,0.5)]">ॐ श्रीं गणेशाय नमः ।</span>
        <span className="text-amber-500 font-extrabold">•</span>
        <span className="mx-6 text-amber-300 drop-shadow-[0_0_8px_rgba(245,158,11,0.5)]">ॐ श्रीं महालक्ष्म्यै नमः ।</span>
        <span className="text-amber-500 font-extrabold">•</span>
        <span className="mx-6 text-amber-300 drop-shadow-[0_0_8px_rgba(245,158,11,0.5)]">विघ्न विनाशाय, धन-समृद्धि प्रदाय नमः ।</span>
        <span className="text-amber-500 font-extrabold">•</span>
      </div>
    </div>
  )
}
