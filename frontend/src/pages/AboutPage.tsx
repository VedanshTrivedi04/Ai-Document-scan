import React from "react"
import { Link } from "react-router-dom"
import { motion } from "framer-motion"
import { Shield, Target, Users, Zap, Lock, BookOpen, ChevronRight } from "lucide-react"

// A simple Navbar just for this page
const Navbar = () => {
  return (
    <header className="fixed top-0 left-0 right-0 z-[100] py-6 bg-white/80 backdrop-blur-md border-b border-gray-100">
      <div className="max-w-7xl mx-auto px-6 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 group">
          <div className="w-10 h-10 flex items-center justify-center group-hover:scale-105 transition-transform overflow-hidden">
            <img src="/logo.png" alt="DocSure Logo" className="w-full h-full object-contain" />
          </div>
          <span className="font-bold text-xl tracking-tighter text-gray-900">DocSure</span>
        </Link>
        <nav className="hidden md:flex items-center gap-10 text-sm font-bold text-gray-600">
          <Link to="/" className="hover:text-blue-600 transition-colors">Home</Link>
          <Link to="/about" className="text-blue-600 transition-colors">About Us</Link>
          <a href="/#how-it-works" className="hover:text-blue-600 transition-colors">How It Works</a>
        </nav>
        <div className="hidden md:flex items-center gap-6">
          <Link to="/login" className="text-sm font-bold text-gray-600 hover:text-blue-600 transition-colors">Log In</Link>
          <Link to="/login" className="bg-blue-600 text-white px-6 py-2.5 rounded-full text-sm font-bold hover:bg-blue-700 transition-all shadow-md">
            Get Started
          </Link>
        </div>
      </div>
    </header>
  )
}

export const AboutPage = () => {
  return (
    <div className="min-h-screen font-sans bg-gray-50 pt-28 selection:bg-blue-500/30 selection:text-blue-900">
      <Navbar />
      
      {/* 1. Hero / Our Mission */}
      <section className="py-20 px-6">
        <div className="max-w-4xl mx-auto text-center space-y-8">
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="inline-flex items-center gap-2 bg-blue-50 text-blue-700 px-4 py-2 rounded-full text-sm font-bold uppercase tracking-widest"
          >
            <Target className="w-4 h-4" />
            Our Mission
          </motion.div>
          <motion.h1 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-5xl md:text-7xl font-bold tracking-tighter text-gray-900 leading-tight"
          >
            To eliminate manual data entry and document fraud for businesses everywhere.
          </motion.h1>
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-xl text-gray-500 font-medium max-w-2xl mx-auto leading-relaxed"
          >
            We believe that verifying truth shouldn't be a bottleneck. DocSure exists to bring instant clarity and absolute trust to every document you process.
          </motion.p>
        </div>
      </section>

      {/* 2. The Story */}
      <section className="py-24 px-6 bg-white border-y border-gray-100">
        <div className="max-w-6xl mx-auto grid md:grid-cols-2 gap-16 items-center">
          <div className="space-y-6">
            <div className="flex items-center gap-3 text-blue-600 font-bold uppercase tracking-widest text-sm mb-4">
              <BookOpen className="w-5 h-5" />
              The Story
            </div>
            <h2 className="text-4xl md:text-5xl font-bold tracking-tighter text-gray-900">Born out of frustration. Built for scale.</h2>
            <p className="text-lg text-gray-600 leading-relaxed">
              We noticed a massive problem in how modern businesses operate: despite the digital revolution, teams were still manually reviewing IDs, cross-referencing PDFs, and fighting an uphill battle against sophisticated document tampering.
            </p>
            <p className="text-lg text-gray-600 leading-relaxed">
              The result? Slow onboarding, human errors, and compromised security. We built DocSure to fix this. By leveraging advanced AI and computer vision, we turned a painstaking manual process into a seamless, automated workflow that takes seconds.
            </p>
          </div>
          <div className="relative h-[400px] rounded-3xl overflow-hidden shadow-2xl border border-gray-100">
             <div className="absolute inset-0 bg-gradient-to-br from-blue-100 to-indigo-50 flex items-center justify-center">
                <div className="grid grid-cols-2 gap-4 p-8 w-full h-full opacity-50">
                  <div className="bg-white rounded-xl shadow-sm border border-blue-100/50" />
                  <div className="bg-white rounded-xl shadow-sm border border-blue-100/50" />
                  <div className="bg-white rounded-xl shadow-sm border border-blue-100/50 col-span-2" />
                </div>
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="bg-white p-6 rounded-2xl shadow-xl flex items-center gap-4">
                    <Shield className="w-10 h-10 text-blue-600" />
                    <div>
                      <div className="text-xl font-bold text-gray-900">10M+</div>
                      <div className="text-sm font-bold text-gray-400 uppercase tracking-widest">Documents Secured</div>
                    </div>
                  </div>
                </div>
             </div>
          </div>
        </div>
      </section>

      {/* 3. Core Values */}
      <section className="py-32 px-6 bg-gray-900 text-white">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-20">
            <h2 className="text-4xl md:text-5xl font-bold tracking-tighter mb-6">Our Core Values</h2>
            <p className="text-xl text-gray-400 max-w-2xl mx-auto font-medium">The principles that guide our technology and our team.</p>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            {[
              { icon: <Lock />, title: "Privacy First", desc: "We never sell your data or use your sensitive documents to train public models. Security isn't a feature, it's our foundation." },
              { icon: <Zap />, title: "Relentless Innovation", desc: "Fraudsters get smarter every day. We move faster. We are constantly upgrading our AI to stay ahead of the curve." },
              { icon: <Target />, title: "Uncompromising Accuracy", desc: "Close enough isn't good enough. We strive for 99.9% accuracy because we know business decisions depend on it." }
            ].map((value, i) => (
              <div key={i} className="bg-gray-800/50 border border-gray-700 p-10 rounded-3xl hover:bg-gray-800 transition-colors">
                <div className="w-14 h-14 bg-gray-700 rounded-2xl flex items-center justify-center text-blue-400 mb-6">
                  {React.cloneElement(value.icon as React.ReactElement, { className: "w-7 h-7" })}
                </div>
                <h3 className="text-2xl font-bold mb-4 text-white">{value.title}</h3>
                <p className="text-gray-400 leading-relaxed font-medium">{value.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 4. Team Section */}
      <section className="py-32 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col md:flex-row justify-between items-end mb-16 gap-6">
            <div>
              <div className="flex items-center gap-3 text-blue-600 font-bold uppercase tracking-widest text-sm mb-4">
                <Users className="w-5 h-5" />
                The Team
              </div>
              <h2 className="text-4xl md:text-5xl font-bold tracking-tighter text-gray-900">Meet the minds behind DocSure.</h2>
            </div>
            <p className="text-lg text-gray-500 max-w-md font-medium">
              We are a team of AI researchers, security engineers, and designers dedicated to solving complex data challenges.
            </p>
          </div>
          
          <div className="grid md:grid-cols-4 gap-6">
            {[
              { name: "Sarah Jenkins", role: "CEO & Co-founder", img: "https://i.pravatar.cc/300?img=47" },
              { name: "David Chen", role: "CTO & Co-founder", img: "https://i.pravatar.cc/300?img=11" },
              { name: "Elena Rodriguez", role: "Head of AI", img: "https://i.pravatar.cc/300?img=32" },
              { name: "Marcus Johnson", role: "Lead Security Architect", img: "https://i.pravatar.cc/300?img=33" }
            ].map((member, i) => (
              <div key={i} className="group cursor-pointer">
                <div className="w-full aspect-square rounded-3xl overflow-hidden mb-6 bg-gray-200">
                  <img src={member.img} alt={member.name} className="w-full h-full object-cover grayscale group-hover:grayscale-0 transition-all duration-500" />
                </div>
                <h3 className="text-xl font-bold text-gray-900">{member.name}</h3>
                <p className="text-blue-600 font-medium">{member.role}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 5. Security & Compliance */}
      <section className="py-24 px-6 bg-blue-600 text-white mt-10">
        <div className="max-w-5xl mx-auto text-center space-y-10">
          <Shield className="w-20 h-20 mx-auto text-blue-200" />
          <h2 className="text-4xl md:text-6xl font-bold tracking-tighter">Bank-grade security as standard.</h2>
          <p className="text-xl text-blue-100 max-w-3xl mx-auto leading-relaxed">
            We operate on a strict <strong>zero-trust, no-logs policy</strong>. Documents are processed in memory and immediately discarded. Data is encrypted in transit and at rest using AES-256. 
            We are fully compliant with GDPR, SOC2 Type II, and HIPAA.
          </p>
          <div className="pt-8">
            <Link to="/login" className="bg-white text-blue-600 px-10 py-5 rounded-full font-bold text-lg hover:bg-gray-100 transition-all shadow-2xl inline-flex items-center gap-2">
              Start Securing Your Workflow <ChevronRight className="w-5 h-5" />
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 border-t border-gray-200 bg-white mt-10">
        <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row justify-between items-center gap-6">
          <div className="flex items-center gap-2">
            <img src="/logo.png" alt="DocSure Logo" className="w-6 h-6 object-contain" />
            <span className="font-bold text-xl text-gray-900">DocSure</span>
          </div>
          <div className="flex gap-8 text-sm font-bold text-gray-500">
            <a href="#" className="hover:text-blue-600 transition-colors">Privacy</a>
            <a href="#" className="hover:text-blue-600 transition-colors">Terms</a>
            <a href="#" className="hover:text-blue-600 transition-colors">Security</a>
          </div>
        </div>
      </footer>
    </div>
  )
}
