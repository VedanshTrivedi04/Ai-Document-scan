import React, { useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { motion } from "framer-motion"
import { ArrowRight, Shield, Search, Menu, X, CheckCircle2, Zap } from "lucide-react"
import { ReactLenis } from "lenis/react"
import gsap from "gsap"
import { ScrollTrigger } from "gsap/ScrollTrigger"

gsap.registerPlugin(ScrollTrigger)

// --- Magnetic Button Component ---
const MagneticButton = ({ children, className, onClick, disabled }: any) => {
  const ref = useRef<HTMLDivElement>(null)
  const [position, setPosition] = useState({ x: 0, y: 0 })

  const handleMouse = (e: React.MouseEvent) => {
    if (disabled) return
    const { clientX, clientY } = e
    const { height, width, left, top } = ref.current!.getBoundingClientRect()
    const middleX = clientX - (left + width / 2)
    const middleY = clientY - (top + height / 2)
    setPosition({ x: middleX * 0.2, y: middleY * 0.2 })
  }
  const reset = () => setPosition({ x: 0, y: 0 })

  return (
    <motion.div
      ref={ref}
      onMouseMove={handleMouse}
      onMouseLeave={reset}
      animate={{ x: position.x, y: position.y }}
      transition={{ type: "spring", stiffness: 150, damping: 15, mass: 0.1 }}
      className={`inline-block ${className}`}
      onClick={onClick}
    >
      {children}
    </motion.div>
  )
}

// --- Navbar ---
const Navbar = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  return (
    <motion.header
      initial={{ y: -100 }}
      animate={{ y: 0 }}
      transition={{ duration: 0.8, ease: "easeOut" }}
      className={`fixed top-0 left-0 right-0 z-[100] py-6 mix-blend-difference text-white pointer-events-none`}
    >
      <div className="max-w-7xl mx-auto px-6 flex items-center justify-between pointer-events-auto">
        <Link to="/" className="flex items-center gap-2 group">
          <div className="w-12 h-12 flex items-center justify-center group-hover:scale-105 transition-transform overflow-hidden">
            <img src="/logo.png" alt="DocSure Logo" className="w-full h-full object-contain" />
          </div>
          <span className="font-bold text-2xl tracking-tighter text-white">DocSure</span>
        </Link>
        <nav className="hidden md:flex items-center gap-10 text-sm font-bold text-white/70">
          <Link to="/about" className="hover:text-white transition-colors">About</Link>
          <a href="#how-it-works" className="hover:text-white transition-colors">How It Works</a>
          <a href="#features" className="hover:text-white transition-colors">Features</a>
          <a href="#faq" className="hover:text-white transition-colors">FAQ</a>
        </nav>
        <div className="hidden md:flex items-center gap-6">
          <Link to="/login?tab=signin" className="text-sm font-bold text-white/70 hover:text-white transition-colors">Log In</Link>
          <MagneticButton>
            <Link to="/login?tab=signup" className="bg-white text-black px-6 py-3 rounded-full text-sm font-bold hover:bg-gray-200 transition-all flex items-center gap-2 shadow-xl">
              Open App
              <ArrowRight className="w-4 h-4" />
            </Link>
          </MagneticButton>
        </div>
        <button className="md:hidden text-white" onClick={() => setMobileMenuOpen(!mobileMenuOpen)}>
          {mobileMenuOpen ? <X /> : <Menu />}
        </button>
      </div>
    </motion.header>
  )
}

// --- Continuous Scroll Story (Scenes 1-9) ---
const CinematicScroll = () => {
  const containerRef = useRef<HTMLDivElement>(null)
  
  // Phase Refs
  const s1TextRef = useRef<HTMLHeadingElement>(null)
  const s2CardsRef = useRef<HTMLDivElement>(null)
  const s3TextRef = useRef<HTMLDivElement>(null)
  const s4ShowcaseRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    if (prefersReducedMotion) return

    let ctx = gsap.context(() => {
      // MASTER TIMELINE
      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: containerRef.current,
          start: "top top",
          end: "+=600%", // Shorter scroll area for faster scrolling
          pin: true,
          scrub: 1.5, // Added smoothing
        }
      })

      // Selectors
      const s1Words = s1TextRef.current?.querySelectorAll(".s1-word")
      const s1Extra = s1TextRef.current?.querySelectorAll(".s1-words")
      const s1Icons = s1TextRef.current?.querySelectorAll(".s1-icon")
      
      const s2Cards = s2CardsRef.current?.querySelectorAll(".s2-card")
      
      const s3Lines = s3TextRef.current?.querySelectorAll(".s3-line")
      
      const s4DocA = s4ShowcaseRef.current?.querySelector(".s4-doc-a")
      const s4DocB = s4ShowcaseRef.current?.querySelector(".s4-doc-b")
      const s4Line = s4ShowcaseRef.current?.querySelector(".s4-line")
      const s4Panel = s4ShowcaseRef.current?.querySelector(".s4-panel")

      // === SCENE 1: Minimalist Opening ===
      // Play opening animation immediately on load, independent of scrolling
      const openingTl = gsap.timeline()
      openingTl.fromTo(s1Words!, { opacity: 0, y: 30 }, { opacity: 1, y: 0, stagger: 0.1, duration: 1.5, ease: "power2.out" })
      openingTl.fromTo(s1Extra!, { opacity: 0, y: 20 }, { opacity: 1, y: 0, stagger: 0.2, duration: 1, ease: "power2.out" }, "-=0.5")
      openingTl.fromTo(s1Icons!, 
        { opacity: 0, scale: 0.5 }, 
        { 
          opacity: 1, 
          scale: 1, 
          stagger: 0.2, 
          duration: 1, 
          ease: "back.out(1.5)",
          onComplete: () => {
             // Start infinite floating animation once they appear
             gsap.to(s1Icons!, {
               y: "-=30", // Slightly reduced distance so faster speed feels natural
               rotation: () => Math.random() * 10 - 5, 
               duration: 1.4, // Faster!
               yoyo: true,
               repeat: -1,
               ease: "power2.inOut", // Smoother parabolic curve
               stagger: {
                 each: 0.2, // Tighter stagger for a more unified flutter
                 from: "random"
               }
             })
          }
        }, 
        "-=1"
      )

      // The scrubbed timeline ONLY handles fading Scene 1 out when the user begins scrolling
      tl.to(s1TextRef.current, { opacity: 0, y: -100, duration: 1, delay: 0.5 }) 

      // === SCENE 2: Floating Document Artwork ===
      tl.fromTo(s2Cards!, 
        { y: "100vh", opacity: 0, rotation: () => Math.random() * 40 - 20, z: -500 }, 
        { y: 0, opacity: 1, rotation: () => Math.random() * 10 - 5, z: 0, stagger: 0.2, duration: 2.5, ease: "power3.out" }
      )
      // They arrange themselves, then all but one fades/moves back
      tl.to(s2CardsRef.current?.querySelectorAll(".s2-small")!, { opacity: 0, scale: 0.5, y: -200, duration: 1, delay: 0.5 })
      tl.to(s2CardsRef.current?.querySelector(".s2-main")!, { opacity: 0, duration: 0.5 }, "-=0.5")

      // === SCENE 3: Hero Typography Transforms ===
      tl.fromTo(s3Lines!, { opacity: 0, y: 50 }, { opacity: 1, y: 0, stagger: 0.3, duration: 1.5 })
      tl.to(s3TextRef.current, { opacity: 0, scale: 0.9, duration: 1, delay: 1 })

      // === SCENE 4 & 5: Full-screen Product Showcase ===
      tl.fromTo(s4ShowcaseRef.current, { opacity: 0, scale: 0.8 }, { opacity: 1, scale: 1, duration: 1 })
      
      // Split into Document A and B
      tl.fromTo(s4DocA!, { x: 100 }, { x: -40, rotation: -3, duration: 1.5, ease: "power2.inOut" }, "split")
      tl.fromTo(s4DocB!, { x: -100 }, { x: 40, rotation: 3, duration: 1.5, ease: "power2.inOut" }, "split")
      
      // Draw connecting line and reveal panel
      tl.fromTo(s4Line!, { scaleY: 0 }, { scaleY: 1, duration: 1, ease: "power1.inOut" })
      tl.fromTo(s4Panel!, { opacity: 0, x: 50 }, { opacity: 1, x: 0, duration: 1 }, "-=0.5")
      
      // Hold scene 5
      tl.to({}, { duration: 1.5 })
      
      // === SCENE 6: Transition Light to Dark ===
      const s1Bg = containerRef.current?.querySelector(".s1-bg")
      tl.to(containerRef.current, { backgroundColor: "#09090b", duration: 1.5 }, "dark")
      tl.to(s1Bg!, { opacity: 0, duration: 1.5 }, "dark")
      tl.to(s4ShowcaseRef.current, { opacity: 0, y: -100, duration: 1.5 }, "dark")


    }, containerRef)

    return () => ctx.revert()
  }, [])

  return (
    <section ref={containerRef} className="h-screen w-full overflow-hidden bg-[#FAFAFA] relative flex items-center justify-center font-sans">
      
      {/* Premium Gradient & Grid Background */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden s1-bg">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#8080801a_1px,transparent_1px),linear-gradient(to_bottom,#8080801a_1px,transparent_1px)] bg-[size:48px_48px] [mask-image:radial-gradient(ellipse_60%_60%_at_50%_50%,#000_70%,transparent_100%)]" />
        <div className="absolute -top-[10%] -left-[10%] w-[50%] h-[50%] bg-purple-300/40 rounded-full blur-[120px] mix-blend-multiply" />
        <div className="absolute top-[10%] -right-[10%] w-[40%] h-[40%] bg-blue-300/40 rounded-full blur-[120px] mix-blend-multiply" />
        <div className="absolute -bottom-[10%] left-[20%] w-[60%] h-[60%] bg-pink-300/30 rounded-full blur-[120px] mix-blend-multiply" />
      </div>

      {/* SCENE 1: Minimalist Opening */}
      <div ref={s1TextRef} className="absolute inset-0 flex flex-col items-center justify-center z-10 px-6">
        <h1 className="text-5xl md:text-8xl font-bold tracking-tighter text-gray-900 text-center max-w-5xl leading-[1.1]">
          {"Every document tells a story.".split(" ").map((word, i) => (
            <span key={i} className="s1-word inline-block mr-3 lg:mr-5">{word}</span>
          ))}
        </h1>
        
        {/* Hero CTA Button */}
        <div className="mt-8 opacity-0 s1-words">
          <MagneticButton>
            <Link to="/login?tab=signup" className="bg-blue-600 text-white px-8 py-4 rounded-full font-bold text-lg hover:bg-blue-700 transition-all shadow-2xl flex items-center gap-2">
              Get Started Free <ArrowRight className="w-5 h-5" />
            </Link>
          </MagneticButton>
        </div>

        {/* Floating Icons */}
        <div className="absolute top-[15%] left-[10%] s1-icon"><img src="/Picsart_26-10-09_11-25-46-807.png" className="w-16 h-16 md:w-20 md:h-20 object-contain drop-shadow-xl" alt="Logo 1" /></div>
        <div className="absolute bottom-[25%] left-[20%] s1-icon"><img src="/Picsart_26-10-09_11-26-27-423.png" className="w-14 h-14 md:w-24 md:h-24 object-contain drop-shadow-2xl" alt="Logo 2" /></div>
        <div className="absolute top-[30%] right-[15%] s1-icon"><img src="/Picsart_26-10-09_11-26-50-538.png" className="w-12 h-12 md:w-16 md:h-16 object-contain drop-shadow-lg" alt="Logo 3" /></div>
        <div className="absolute bottom-[20%] right-[25%] s1-icon"><img src="/Picsart_26-10-09_11-27-15-475.png" className="w-20 h-20 md:w-28 md:h-28 object-contain drop-shadow-2xl" alt="Logo 4" /></div>
        <div className="absolute top-[10%] right-[35%] s1-icon"><img src="/Picsart_26-10-09_11-27-39-573.png" className="w-10 h-10 md:w-14 md:h-14 object-contain drop-shadow-md" alt="Logo 5" /></div>
        <div className="absolute bottom-[10%] left-[40%] s1-icon"><img src="/Picsart_26-10-09_11-28-12-604.png" className="w-16 h-16 md:w-20 md:h-20 object-contain drop-shadow-xl" alt="Logo 6" /></div>
        
        {/* Trusted By Marquee */}
        <div className="absolute bottom-12 w-full flex flex-col items-center justify-center opacity-0 s1-words">
          <p className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-6">Trusted by startups, businesses & global teams</p>
          <div className="w-full max-w-5xl overflow-hidden relative [mask-image:_linear-gradient(to_right,transparent_0,_black_128px,_black_calc(100%-128px),transparent_100%)]">
             <motion.div
                animate={{ x: ["0%", "-50%"] }}
                transition={{ duration: 20, ease: "linear", repeat: Infinity }}
                className="flex items-center gap-16 w-max"
             >
                {[
                  "/Picsart_26-10-09_11-25-46-807.png",
                  "/Picsart_26-10-09_11-26-27-423.png",
                  "/Picsart_26-10-09_11-26-50-538.png",
                  "/Picsart_26-10-09_11-27-15-475.png",
                  "/Picsart_26-10-09_11-27-39-573.png",
                  "/Picsart_26-10-09_11-28-12-604.png",
                  "/Picsart_26-10-09_11-28-33-636.png",
                  "/Picsart_26-10-09_11-29-27-971.png",
                  "/Picsart_26-10-09_11-29-47-971.png",
                  "/Picsart_26-10-09_11-30-16-123.png",
                  "/Picsart_26-10-09_11-30-35-841.png"
                ].map((src, i) => (
                  <img key={i} src={src} className="h-8 md:h-10 object-contain grayscale opacity-60 hover:grayscale-0 hover:opacity-100 transition-all" alt="Partner Logo" />
                ))}
                {/* Duplicate for infinite seamless scroll */}
                {[
                  "/Picsart_26-10-09_11-25-46-807.png",
                  "/Picsart_26-10-09_11-26-27-423.png",
                  "/Picsart_26-10-09_11-26-50-538.png",
                  "/Picsart_26-10-09_11-27-15-475.png",
                  "/Picsart_26-10-09_11-27-39-573.png",
                  "/Picsart_26-10-09_11-28-12-604.png",
                  "/Picsart_26-10-09_11-28-33-636.png",
                  "/Picsart_26-10-09_11-29-27-971.png",
                  "/Picsart_26-10-09_11-29-47-971.png",
                  "/Picsart_26-10-09_11-30-16-123.png",
                  "/Picsart_26-10-09_11-30-35-841.png"
                ].map((src, i) => (
                  <img key={`dup-${i}`} src={src} className="h-8 md:h-10 object-contain grayscale opacity-60 hover:grayscale-0 hover:opacity-100 transition-all" alt="Partner Logo" />
                ))}
             </motion.div>
          </div>
        </div>
      </div>

      {/* SCENE 2: Floating Documents */}
      <div ref={s2CardsRef} className="absolute inset-0 flex items-center justify-center z-20 pointer-events-none perspective-1000">
        <div className="relative w-full max-w-4xl h-[700px] flex items-center justify-center" style={{ transformStyle: "preserve-3d" }}>
          <div className="s2-card s2-small absolute top-[10%] left-[10%] w-64 h-80 bg-white rounded-xl shadow-xl border border-gray-100 z-10 opacity-0 overflow-hidden flex flex-col">
             <img src="/licence.png" alt="Licence Document" className="w-full h-full object-cover" />
          </div>
          <div className="s2-card s2-small absolute bottom-[15%] right-[5%] w-72 h-96 bg-white rounded-xl shadow-2xl border border-gray-100 z-30 opacity-0 flex flex-col overflow-hidden">
             <img src="/images.png" alt="Document" className="w-full h-full object-cover" />
          </div>
          <div className="s2-card s2-small absolute top-[20%] right-[15%] w-56 h-72 bg-white rounded-xl shadow-lg border border-gray-100 p-6 z-0 opacity-0 flex flex-col">
             <div className="flex items-center gap-3 mb-6">
               <div className="w-10 h-10 rounded-lg bg-green-50 flex items-center justify-center">
                 <div className="w-4 h-4 rounded-sm bg-green-400" />
               </div>
               <div>
                 <div className="w-16 h-2 bg-gray-200 rounded mb-2" />
                 <div className="w-24 h-3 bg-gray-800 rounded" />
               </div>
             </div>
             <div className="w-full h-24 bg-gradient-to-br from-gray-50 to-gray-100 rounded-lg mb-4 border border-gray-100 flex items-center justify-center relative overflow-hidden">
                <svg className="w-full h-full text-green-200 absolute bottom-0 translate-y-2" viewBox="0 0 100 40" preserveAspectRatio="none">
                  <path d="M0 40 L0 20 Q 25 35 50 20 T 100 10 L100 40 Z" fill="currentColor" opacity="0.5"/>
                  <path d="M0 40 L0 25 Q 25 40 50 25 T 100 5 L100 40 Z" fill="currentColor"/>
                </svg>
             </div>
             <div className="space-y-2 mt-auto">
               <div className="flex justify-between"><div className="w-1/2 h-2 bg-gray-100 rounded"/><div className="w-4 h-2 bg-green-400 rounded"/></div>
               <div className="flex justify-between"><div className="w-2/3 h-2 bg-gray-100 rounded"/><div className="w-4 h-2 bg-green-400 rounded"/></div>
             </div>
          </div>
          <div className="s2-card s2-small absolute bottom-[10%] left-[20%] w-80 h-64 bg-white rounded-xl shadow-2xl border border-gray-100 z-20 opacity-0 overflow-hidden flex flex-col">
             <img src="/aadhar.png" alt="Aadhar Document" className="w-full h-full object-cover" />
          </div>
          
          <div className="s2-card s2-main w-full max-w-xl bg-white rounded-2xl shadow-[0_30px_60px_-15px_rgba(0,0,0,0.1)] border border-gray-100 p-8 z-40 opacity-0 relative overflow-hidden flex flex-col font-sans">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-500 via-indigo-500 to-purple-500" />
            
            <div className="flex justify-between items-start mb-8">
              <div>
                <h3 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                  <Shield className="w-5 h-5 text-blue-500" />
                  Authentication Report
                </h3>
                <p className="text-sm text-gray-500 mt-1">ID: #DOC-8492-X</p>
              </div>
              <div className="flex gap-2">
                <span className="px-3 py-1 bg-green-50 text-green-700 text-xs font-bold uppercase tracking-wider rounded-full border border-green-200">Verified</span>
                <span className="px-3 py-1 bg-blue-50 text-blue-700 text-xs font-bold uppercase tracking-wider rounded-full border border-blue-200">High Trust</span>
              </div>
            </div>
            
            <div className="flex gap-6 mb-8">
              <div className="flex-1 space-y-4">
                <div className="flex justify-between items-center border-b border-gray-50 pb-2">
                  <span className="text-sm text-gray-500">Document Type</span>
                  <span className="text-sm font-semibold text-gray-900">Identity Card</span>
                </div>
                <div className="flex justify-between items-center border-b border-gray-50 pb-2">
                  <span className="text-sm text-gray-500">Issuer</span>
                  <span className="text-sm font-semibold text-gray-900">Gov. Authority</span>
                </div>
                <div className="flex justify-between items-center pb-2">
                  <span className="text-sm text-gray-500">Confidence Score</span>
                  <span className="text-sm font-bold text-blue-600">98.5%</span>
                </div>
              </div>
              
              <div className="w-32 h-32 bg-gray-50 rounded-xl border border-gray-100 flex flex-col items-center justify-center relative shrink-0">
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-2xl font-black text-gray-900">98</span>
                  <span className="text-[10px] uppercase font-bold text-gray-400">Score</span>
                </div>
                <svg className="w-24 h-24 transform -rotate-90 drop-shadow-sm">
                  <circle cx="48" cy="48" r="40" stroke="currentColor" strokeWidth="6" fill="transparent" className="text-gray-200" />
                  <circle cx="48" cy="48" r="40" stroke="currentColor" strokeWidth="6" fill="transparent" strokeDasharray="251.2" strokeDashoffset="5" className="text-blue-500" />
                </svg>
              </div>
            </div>
            
            <div className="bg-gray-50 p-4 rounded-xl border border-gray-100 flex items-start gap-3 mt-auto">
              <CheckCircle2 className="w-5 h-5 text-green-500 shrink-0 mt-0.5" />
              <div>
                <h4 className="text-sm font-bold text-gray-900">All checks passed</h4>
                <p className="text-xs text-gray-500 mt-1 leading-relaxed">No anomalies detected in fonts, holograms, or MRZ zones. The document is authentic and has not been altered.</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* SCENE 3: Hero Typography Transforms */}
      <div ref={s3TextRef} className="absolute inset-0 flex flex-col items-center justify-center z-30 px-6 pointer-events-none">
        <h2 className="s3-line text-6xl md:text-8xl font-bold tracking-tighter text-gray-900 text-center leading-tight mb-8">
          Find what <span className="text-blue-600 relative inline-block">
            doesn't add up.
            <span className="absolute bottom-1 left-0 w-full h-2 bg-blue-100 -z-10 rounded-full opacity-50"></span>
          </span>
        </h2>
        <p className="s3-line text-xl md:text-2xl text-gray-500 font-medium text-center max-w-2xl">
          Compare documents. Discover contradictions. Follow the evidence.
        </p>
      </div>

      {/* SCENE 4 & 5: Full-screen Product Showcase */}
      <div ref={s4ShowcaseRef} className="absolute inset-0 flex items-center justify-center z-40 opacity-0 pointer-events-auto">
        <div className="relative w-full max-w-5xl h-[600px] flex items-center justify-center">
          
          {/* Doc A */}
          <div className="s4-doc-a absolute left-[10%] w-[350px] h-auto bg-white rounded-2xl shadow-2xl border border-gray-100 origin-bottom-left z-10 overflow-hidden flex flex-col">
             <img src="/c2.jpeg" alt="Master Agreement.pdf" className="w-full h-auto object-contain block" />
          </div>

          {/* Connection Line */}
          <div className="s4-line absolute w-0.5 h-64 bg-red-400 origin-top z-0" />

          {/* Doc B */}
          <div className="s4-doc-b absolute right-[10%] top-[15%] w-[350px] h-auto bg-white rounded-2xl shadow-2xl border border-gray-100 origin-top-right z-20 overflow-hidden flex flex-col">
             <img src="/c3.jpeg" alt="Project Schedule.pdf" className="w-full h-auto object-contain block" />
          </div>
          
          {/* Analysis Panel */}
          <div className="s4-panel absolute bottom-[5%] right-[20%] w-96 bg-black/80 backdrop-blur-2xl text-white p-8 rounded-3xl shadow-[0_0_50px_-12px_rgba(59,130,246,0.5)] border border-white/10 z-30 flex flex-col gap-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center border border-blue-500/30">
                  <Shield className="w-5 h-5 text-blue-400" />
                </div>
                <div className="text-xs font-bold uppercase tracking-widest text-blue-400">Analysis Result</div>
              </div>
              <div className="flex items-center gap-2">
                <span className="relative flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
                </span>
                <span className="text-xs font-bold text-red-400 uppercase tracking-widest">Alert</span>
              </div>
            </div>
            
            <div className="space-y-2">
              <h3 className="text-white font-black text-2xl leading-tight">Potential contradiction detected</h3>
              <p className="text-base text-zinc-400 leading-relaxed font-medium">Both documents specify different project deadlines for the final deliverables.</p>
            </div>
            
            <div className="mt-4 p-4 rounded-xl bg-white/5 border border-white/10 flex flex-col gap-3">
               <div className="flex justify-between items-center text-sm font-medium">
                 <span className="text-zinc-500">Master Agreement:</span>
                 <span className="text-red-400 bg-red-400/10 px-2 py-1 rounded-md">15 Sep 2026</span>
               </div>
               <div className="w-full h-[1px] bg-white/10"></div>
               <div className="flex justify-between items-center text-sm font-medium">
                 <span className="text-zinc-500">Project Schedule:</span>
                 <span className="text-red-400 bg-red-400/10 px-2 py-1 rounded-md">30 Sep 2026</span>
               </div>
            </div>

            <div className="mt-2 pt-4 border-t border-white/10 text-[10px] text-zinc-500 uppercase font-bold tracking-widest flex items-center gap-2">
              <Zap className="w-3 h-3" /> Sample Demonstration
            </div>
          </div>
        </div>
      </div>

    </section>
  )
}

// --- SCENE 10: Practical Sections ---
const PracticalSections = () => {
  return (
    <div className="bg-[#09090b] text-zinc-200 py-32 px-6">
      <div className="max-w-7xl mx-auto space-y-40">
        
        {/* Key Features (Why DocSure?) */}
        <section id="features" className="scroll-mt-32 relative flex flex-col md:flex-row gap-16 items-start">
          {/* Left side (Sticky) */}
          <div className="md:w-1/3 md:sticky md:top-32 shrink-0">
            <h3 className="text-sm font-bold uppercase tracking-widest text-zinc-500 mb-4">Why DocSure?</h3>
            <h2 className="text-4xl md:text-6xl font-bold tracking-tighter text-white">Key Features</h2>
            <p className="text-xl text-zinc-400 mt-6 leading-relaxed">
              Discover how our AI-powered platform automates manual reviews and catches fraud before it impacts your business.
            </p>
          </div>
          
          {/* Right side (Scrolling) */}
          <div className="md:w-2/3 flex flex-col gap-16 md:gap-32">
            {[
              { icon: <Zap />, title: "Real-time OCR", desc: "Extract data from documents instantly with high accuracy." },
              { icon: <Search />, title: "Fraud Detection", desc: "Identify forged or tampered documents automatically." },
              { icon: <Shield />, title: "Bank-grade Security", desc: "Your data is encrypted and handled with the highest security standards." },
              { icon: <CheckCircle2 />, title: "Contradiction Detect", desc: "Our core AI detects logical conflicts between multiple documents." },
            ].map((f, i) => (
              <div key={i} className="bg-zinc-900/50 border border-zinc-800 p-10 md:p-14 rounded-3xl hover:bg-zinc-900 transition-colors shadow-2xl">
                <div className="w-16 h-16 bg-zinc-800 rounded-2xl flex items-center justify-center text-zinc-300 mb-8">{React.cloneElement(f.icon as any, { className: "w-8 h-8 text-blue-400" })}</div>
                <h4 className="text-3xl font-bold text-white mb-4">{f.title}</h4>
                <p className="text-lg text-zinc-400 font-medium leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* How It Works */}
        <section id="how-it-works" className="scroll-mt-32">
          <div className="bg-zinc-900 border border-zinc-800 rounded-[3rem] p-10 md:p-20">
             <h3 className="text-sm font-bold uppercase tracking-widest text-zinc-500 mb-4">How It Works</h3>
             <h2 className="text-4xl md:text-5xl font-bold tracking-tighter text-white mb-16">Three steps to truth.</h2>
             
             <div className="grid md:grid-cols-3 gap-12">
               {[
                 { step: "01", title: "Upload Files", desc: "Drag and drop your PDFs into the secure platform." },
                 { step: "02", title: "AI Scanning", desc: "The engine reads and cross-references all claims." },
                 { step: "03", title: "Resolve", desc: "Review the evidence side-by-side in your queue." }
               ].map((s, i) => (
                 <div key={i} className="relative">
                   <div className="text-7xl font-black text-zinc-800 mb-6">{s.step}</div>
                   <h4 className="text-2xl font-bold text-white mb-3">{s.title}</h4>
                   <p className="text-zinc-400 font-medium leading-relaxed">{s.desc}</p>
                 </div>
               ))}
             </div>
          </div>
        </section>

        {/* CTA Section */}
        <section className="relative flex flex-col items-center justify-center text-white py-32 px-6 rounded-[3rem] overflow-hidden border border-zinc-800 bg-zinc-900/50">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom,_var(--tw-gradient-stops))] from-blue-900/20 via-black/0 to-black/0 pointer-events-none" />
          <div className="max-w-4xl text-center space-y-8 relative z-10">
            <h2 className="text-6xl md:text-8xl font-bold tracking-tighter text-white">Clarity begins with <span className="text-zinc-500">consistency.</span></h2>
            <p className="text-xl md:text-2xl text-zinc-400 max-w-2xl mx-auto font-medium leading-relaxed">
              Find conflicting information, inspect the evidence, and make better-informed decisions with DocSure.
            </p>
            <div className="pt-8 flex justify-center">
              <MagneticButton>
                <Link to="/login?tab=signup" className="bg-white text-black px-12 py-6 rounded-full font-bold text-xl hover:bg-gray-200 transition-colors inline-flex items-center gap-3">
                  Start Analyzing <ArrowRight className="w-6 h-6" />
                </Link>
              </MagneticButton>
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="border-t border-zinc-800 pt-10 flex flex-col md:flex-row justify-between items-center gap-6">
          <div className="flex items-center gap-2">
            <img src="/logo.png" alt="DocSure Logo" className="w-6 h-6 object-contain" />
            <span className="font-bold text-xl text-white">DocSure</span>
          </div>
          <div className="flex gap-8 text-sm font-bold text-zinc-500">
            <a href="#" className="hover:text-white transition-colors">Privacy</a>
            <a href="#" className="hover:text-white transition-colors">Terms</a>
            <a href="#" className="hover:text-white transition-colors">Security</a>
          </div>
        </footer>
      </div>
    </div>
  )
}

export const LandingPage = () => {
  return (
    <ReactLenis root>
      <div className="min-h-screen font-sans selection:bg-blue-500/30 selection:text-blue-200">
        <Navbar />
        <main>
          <CinematicScroll />
          <PracticalSections />
        </main>
      </div>
    </ReactLenis>
  )
}
