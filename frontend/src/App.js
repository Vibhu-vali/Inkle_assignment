import { useState } from "react";
import "@/App.css";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { MapPin, Loader2 } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [place, setPlace] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!place.trim()) {
      setError("Please enter a place name");
      return;
    }

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
    }
  };

  return (
    <div className="app-container">
      <div className="content-wrapper">
        <div className="header-section">
          <div className="icon-wrapper">
            <MapPin className="icon" />
          </div>
          <h1 className="title">Tourism Planner</h1>
          <p className="subtitle">Discover weather and attractions for any destination</p>
        </div>

        <form onSubmit={handleSubmit} className="search-form">
          <div className="input-group">
            <Input
              data-testid="place-input"
              type="text"
              placeholder="Enter a place you want to visit..."
              value={place}
              onChange={(e) => setPlace(e.target.value)}
              disabled={loading}
              className="place-input"
            />
            <Button 
              data-testid="search-button"
              type="submit" 
              disabled={loading}
              className="search-button"
            >
              {loading ? (
                <>
                  <Loader2 className="animate-spin mr-2" size={18} />
                  Searching...
                </>
              ) : (
                "Explore"
              )}
            </Button>
          </div>
        </form>

        {error && (
          <Card className="result-card error-card" data-testid="error-message">
            <CardContent className="card-content">
              <p className="error-text">❌ {error}</p>
            </CardContent>
          </Card>
        )}

        {result && (
          <Card className="result-card" data-testid="result-card">
            <CardContent className="card-content">
              <pre className="result-text">{result.message}</pre>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

export default App;