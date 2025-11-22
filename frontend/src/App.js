import { useState, useCallback, useRef } from "react";
import "@/App.css";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { MapPin, Loader2 } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";
const API = BACKEND_URL ? `${BACKEND_URL}/api` : "/api";

function App() {
  const [place, setPlace] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const isSubmitting = useRef(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (isSubmitting.current) return; // Prevent duplicate submissions
    
    if (!place.trim()) {
      setError("Please enter a place name");
      return;
    }

    isSubmitting.current = true;
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await axios.post(`${API}/tourism/query`, {
        place: place.trim()
      });

      if (response.data.success) {
        setResult(response.data);
      } else {
        setError(response.data.message);
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to fetch information. Please try again.");
    } finally {
      setLoading(false);
      isSubmitting.current = false;
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-pink-800 relative overflow-hidden">
      {/* Animated Background Elements */}
      <div className="absolute inset-0">
        <div className="absolute top-20 left-20 w-72 h-72 bg-purple-300 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-pulse"></div>
        <div className="absolute top-40 right-20 w-72 h-72 bg-yellow-300 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-pulse animation-delay-2000"></div>
        <div className="absolute -bottom-8 left-40 w-72 h-72 bg-pink-300 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-pulse animation-delay-4000"></div>
      </div>

      <div className="relative z-10 container mx-auto px-4 py-8 max-w-5xl">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center justify-center w-24 h-24 bg-gradient-to-r from-cyan-400 via-blue-500 to-purple-600 rounded-full mb-8 shadow-2xl transform hover:scale-110 transition-transform duration-300">
            <MapPin className="w-12 h-12 text-white drop-shadow-lg" />
          </div>
          <h1 className="text-6xl font-black bg-gradient-to-r from-cyan-300 via-blue-400 to-purple-400 bg-clip-text text-transparent mb-6 tracking-tight">
            Tourism Planner
          </h1>
          <p className="text-xl text-gray-200 max-w-3xl mx-auto leading-relaxed">
            🌍 Discover weather and attractions for any destination around the world
          </p>
        </div>

        {/* Search Form */}
        <form onSubmit={handleSubmit} className="mb-12">
          <div className="flex flex-col lg:flex-row gap-6 max-w-4xl mx-auto">
            <div className="flex-1 relative group">
              <div className="absolute inset-y-0 left-0 pl-6 flex items-center pointer-events-none">
                <MapPin className="h-6 w-6 text-purple-300 group-focus-within:text-white transition-colors duration-200" />
              </div>
              <Input
                data-testid="place-input"
                type="text"
                placeholder="🔍 Enter your dream destination (e.g., Bali, Paris, Tokyo)..."
                value={place}
                onChange={(e) => setPlace(e.target.value)}
                disabled={loading}
                className="pl-14 pr-6 h-16 text-xl bg-white/10 backdrop-blur-md border-2 border-white/20 rounded-2xl focus:border-cyan-400 focus:ring-4 focus:ring-cyan-400/30 transition-all duration-300 text-white placeholder-gray-300 shadow-2xl"
              />
              <div className="absolute inset-0 rounded-2xl bg-gradient-to-r from-cyan-400/20 to-purple-400/20 opacity-0 group-focus-within:opacity-100 transition-opacity duration-300 pointer-events-none"></div>
            </div>
            <Button 
              data-testid="search-button"
              type="submit" 
              disabled={loading || !place.trim()}
              className="h-16 px-10 bg-gradient-to-r from-cyan-500 via-blue-500 to-purple-600 hover:from-cyan-600 hover:via-blue-600 hover:to-purple-700 text-white font-bold text-lg rounded-2xl shadow-2xl hover:shadow-cyan-500/50 transform hover:scale-105 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none relative overflow-hidden group"
            >
              <div className="absolute inset-0 bg-gradient-to-r from-white/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
              {loading ? (
                <>
                  <Loader2 className="animate-spin mr-3" size={24} />
                  <span>Searching...</span>
                </>
              ) : (
                <>
                  <span className="mr-2">✈️</span>
                  <span>Explore</span>
                </>
              )}
            </Button>
          </div>
        </form>

        {/* Error Message */}
        {error && (
          <div className="mb-8 animate-fadeIn">
            <Card className="border-red-500/50 bg-red-900/50 backdrop-blur-md shadow-2xl shadow-red-500/20" data-testid="error-message">
              <CardContent className="p-6">
                <div className="flex items-center text-red-200">
                  <div className="w-12 h-12 bg-red-500/20 rounded-full flex items-center justify-center mr-4 animate-pulse">
                    <span className="text-2xl">⚠️</span>
                  </div>
                  <p className="font-medium text-lg">{error}</p>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Result Card */}
        {result && (
          <div className="animate-fadeIn">
            <Card className="shadow-2xl border-0 bg-white/10 backdrop-blur-md overflow-hidden" data-testid="result-card">
              <div className="bg-gradient-to-r from-cyan-500/20 to-purple-500/20 p-6 border-b border-white/10">
                <div className="flex items-center">
                  <div className="w-16 h-16 bg-gradient-to-r from-green-400 to-blue-500 rounded-2xl flex items-center justify-center mr-6 shadow-xl">
                    <span className="text-3xl">📍</span>
                  </div>
                  <div>
                    <h2 className="text-3xl font-bold text-white mb-2">{result.place}</h2>
                    <p className="text-gray-300 flex items-center">
                      <span className="mr-2">🌐</span>
                      Coordinates: {result.coordinates?.lat.toFixed(4)}, {result.coordinates?.lon.toFixed(4)}
                    </p>
                  </div>
                </div>
              </div>
              
              <CardContent className="p-8">
                <div className="result-text space-y-6">
                  {result.message.split('\n').map((line, index) => {
                    // Main heading with place name
                    if (line.includes('In') && (line.includes('it\'s currently') || line.includes('these are the places'))) {
                      return (
                        <div key={index} className="text-gray-100 text-lg font-semibold mb-6">
                          {line}
                        </div>
                      );
                    }
                    // Weather information
                    else if (line.includes('it\'s currently')) {
                      return (
                        <div key={index} className="text-gray-200 text-base mb-4">
                          {line}
                        </div>
                      );
                    }
                    // Places heading
                    else if (line.includes('these are the places you can go')) {
                      return (
                        <div key={index} className="mt-8">
                          <h3 className="text-gray-100 text-lg font-semibold mb-6 flex items-center">
                            <span className="text-2xl mr-3 animate-bounce">🎯</span>
                            {line}
                          </h3>
                        </div>
                      );
                    }
                    // Individual places
                    else if (line.trim() && !line.includes('In') && !line.includes('And')) {
                      // Find matching place data with Wikipedia URL
                      const placeData = result.places_data?.find(p => 
                        p.name === line.trim()
                      );
                      
                      console.log('Place line:', line);
                      console.log('Found place data:', placeData);
                      
                      return (
                        <div key={index} className="ml-8">
                          <div 
                            className="flex items-center bg-white/10 backdrop-blur-sm rounded-2xl p-5 border border-white/20 hover:bg-white/20 transform hover:scale-105 transition-all duration-300 cursor-pointer group"
                            onClick={() => {
                              console.log('Clicked place:', placeData);
                              if (placeData?.wikipedia_url) {
                                window.open(placeData.wikipedia_url, '_blank');
                              } else {
                                // Fallback: search Wikipedia for the place name
                                const searchUrl = `https://en.wikipedia.org/wiki/Special:Search?search=${encodeURIComponent(line)}`;
                                window.open(searchUrl, '_blank');
                              }
                            }}
                          >
                            <span className="text-2xl mr-4 group-hover:scale-125 transition-transform duration-300">📍</span>
                            <div className="flex-1">
                              <p className="text-base font-medium text-gray-200 group-hover:text-cyan-300 transition-colors duration-300">{line}</p>
                              <p className="text-gray-400 text-sm">Click to learn more → Wikipedia</p>
                            </div>
                            <span className="text-gray-400 group-hover:text-white transition-colors duration-300">🔗</span>
                          </div>
                        </div>
                      );
                    }
                    // Other text
                    else if (line.trim()) {
                      return (
                        <div key={index} className="text-gray-200 text-base">
                          {line}
                        </div>
                      );
                    }
                    return null;
                  })}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Footer */}
        <div className="text-center mt-16 text-gray-400">
          <p className="text-sm">✨ Made with ❤️ for travelers worldwide ✨</p>
        </div>
      </div>

      <style jsx>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fadeIn {
          animation: fadeIn 0.5s ease-out;
        }
        .animation-delay-2000 {
          animation-delay: 2s;
        }
        .animation-delay-4000 {
          animation-delay: 4s;
        }
      `}</style>
    </div>
  );
}

export default App;