# verity-misinformation-tracker
An AI-based misinformation evolution tracking system using NLP. Currently under active development.
# Verity — AI-Based Misinformation Evolution Tracker

**Verity** is an AI-based misinformation tracking system designed to analyze claims, identify similarities between narratives, and track how information evolves across different sources over time.

The project uses Natural Language Processing (NLP) techniques to analyze textual content and visualize relationships between claims through an interactive evolution graph and timeline.

> **Project Status: Under Development**
>
> Verity is currently being developed as a college mini-project. Its features and functionality are still being improved, tested, and expanded. This repository represents an ongoing development version, not the final release.

---

## Overview

Misinformation spreads rapidly across digital platforms, often changing its wording and presentation as it moves between sources.

Verity aims to help users understand these changes by analyzing submitted claims, extracting relevant information, comparing narratives, and visualizing their relationships.

Rather than simply classifying information as true or false, Verity focuses on tracking similarities and the evolution of narratives.

## Features

The current implementation includes the following functionality:

- **Text Analysis:** Submit textual claims, headlines, or articles for NLP-based analysis.
- **Image Analysis (OCR):** Extract text from uploaded images using Optical Character Recognition.
- **Keyword Extraction:** Identify important terms using TF-IDF.
- **Named Entity Recognition:** Extract people, organizations, and locations using spaCy.
- **Sentiment Analysis:** Analyze the polarity and subjectivity of textual content.
- **Narrative Similarity:** Compare claims using cosine similarity.
- **Claim Clustering:** Group related claims using clustering techniques.
- **Evolution Graph:** Visualize relationships between claims through an interactive graph.
- **Timeline Visualization:** Explore tracked claims chronologically.
- **News Tracking:** Search and analyze news topics using the NewsAPI integration.
- **Claim Verification:** Retrieve available independent fact-check reviews using Google's Fact Check Tools API.
- **User Authentication:** Register, log in, and maintain user-specific search history.

*Note: Feature availability may depend on API configuration and the current development state.*

## Technologies Used

| Component | Technologies |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python, Flask |
| Database | SQLite, Flask-SQLAlchemy |
| NLP | spaCy, Scikit-learn, TextBlob |
| Machine Learning | TF-IDF, Cosine Similarity, DBSCAN |
| Image Processing | Tesseract OCR, Pytesseract |
| Authentication | Flask-JWT-Extended, bcrypt |
| External APIs | NewsAPI, Google Fact Check Tools API |

## Project Structure

```text
verity/
│
├── backend/
│   ├── app.py
│   ├── config.py
│   ├── extensions.py
│   ├── models.py
│   ├── requirements.txt
│   │
│   ├── nlp/
│   ├── ocr/
│   ├── routes/
│   ├── services/
│   └── instance/
│
├── frontend/
│   ├── templates/
│   └── static/
│
├── setup.bat
├── run.bat
├── setup.sh
├── run.sh
├── .gitignore
└── README.md
```

## Installation and Setup

### Prerequisites

- Python 3.10 or higher
- Git
- Tesseract OCR (optional, required for image analysis)
- Internet connection for installing dependencies and accessing external APIs

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR-USERNAME/verity-misinformation-tracker.git
```

```bash
cd verity-misinformation-tracker
```

### 2. Set Up the Environment

**Windows:**

```bash
setup.bat
```

**macOS / Linux:**

```bash
./setup.sh
```

The setup script creates a Python virtual environment, installs the required dependencies, installs the spaCy English language model, and creates the environment configuration file if it does not already exist.

### 3. Configure Environment Variables

The project uses environment variables for API keys and application configuration.

A sample configuration file is provided at:

```text
backend/.env.example
```

The setup script creates:

```text
backend/.env
```

Add your own API keys where required.

Available integrations include:

- NewsAPI
- Google Fact Check Tools API

**Important:** Never upload your actual `.env` file or expose API keys publicly.

### 4. Run the Application

**Windows:**

```bash
run.bat
```

**macOS / Linux:**

```bash
./run.sh
```

### 5. Access the Application

Open your browser and visit:

```text
http://localhost:5000
```

The frontend and backend are served through the same Flask application.

## Current Limitations

As the project is still under development:

- Some planned features may not yet be implemented.
- Analysis results depend on the available data and configured APIs.
- Live news tracking requires a valid NewsAPI key.
- Claim verification requires a valid Google Fact Check Tools API key.
- Image analysis requires Tesseract OCR to be installed.
- Narrative similarity does not establish whether a claim is factually true or false.

## Future Improvements

Planned areas of improvement include:

- Enhancing misinformation detection and narrative tracking.
- Improving image-based misinformation analysis.
- Improving graph visualization and user interaction.
- Expanding the dataset of tracked claims.
- Improving analysis accuracy and performance.
- Adding further features and refining the user interface.

## Disclaimer

Verity is an academic project intended for educational and research purposes.

Similarity scores and NLP-generated analysis should not be treated as definitive proof of misinformation. Independent fact-checking and verification are important when evaluating the credibility of claims.

---

**Developed as a College Mini-Project**

*Verity — Tracking the Evolution of Misinformation.*
