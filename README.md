# ISECO - Intelligent Smart Expense & Goal Companion

An advanced Django-based financial management system powered by AI, designed to help users track expenses, manage financial goals, optimize spending, and make data-driven financial decisions.

## 🌟 Key Features

### Expense Management
- Track income and expenses with detailed categorization
- Real-time expense monitoring and analysis
- Flexible filtering and search capabilities
- Transaction history and reporting

### 🤖 AI-Powered Intelligence (Ollama LLM 3.2)
**Advanced Natural Language Processing with Llama 3.2 Large Language Model**
- **Intelligent Financial Insights**: LLM-generated contextual analysis of financial situations
- **Natural Language Suggestions**: AI-generated recommendations in conversational format
- **Smart Explanations**: Complex financial concepts explained in user-friendly language
- **Context-Aware Guidance**: Personalized financial advice based on individual spending patterns
- **Dynamic Strategy Generation**: AI-crafted monthly strategies with reasoning and rationale
- **Anomaly Explanation**: Natural language explanation of unusual spending patterns
- **Goal Advisory**: Intelligent counseling on goal feasibility and alternative approaches

### 🧠 Machine Learning Analytics & Optimization
**Powered by scikit-learn, NumPy, and SciPy**
- **Smart Forecasting**: Advanced ML models for predicting future savings and spending trends
- **Goal Feasibility Analysis**: Statistical analysis of whether financial goals are mathematically achievable
- **Spending Optimization**: Intelligent budget allocation using priority and constraint-based optimization
- **Overspending Detection**: ML-based anomaly detection for unusual spending patterns
- **Spending Clustering**: Unsupervised learning to identify and categorize spending patterns
- **Trend Analysis**: Statistical analysis of spending trends over time
- **Predictive Modeling**: Regression models for accurate savings forecasting

### Goal Management
- Create and track financial goals with deadlines
- Priority-based goal scheduling
- Feasibility assessment with next achievable date suggestions
- Multi-goal planning and optimization
- Goal progress tracking

### Analytics & Insights
- Comprehensive financial analytics dashboard
- Spending trend analysis
- Income vs. expense visualization
- Goal-based financial insights
- Monthly average calculations

### Collaboration & Sharing
- Group management for shared financial goals
- User profiles and authentication
- Notification system for goal milestones and alerts

## 📋 Project Structure

```
FINANCE/
├── broenv/                 # Python virtual environment
├── finance/                # Django project root
    ├── manage.py          # Django management utility
    ├── db.sqlite3         # SQLite database
    │
    ├── finance/           # Main project settings
    │   ├── settings.py    # Django configuration
    │   ├── urls.py        # URL routing
    │   ├── wsgi.py        # WSGI application
    │   └── asgi.py        # ASGI application
    │
    └── Apps:
        ├── users/         # User authentication & management
        ├── expenses/      # Expense tracking & management
        ├── goals/         # Goal management & feasibility engine
        ├── ai_engine/     # AI modules for insights & predictions
        ├── analytics/     # Financial analytics & reporting
        ├── groups/        # Group management
        └── notifications/ # Notification system
```

## 🏗️ App Overview

### `users`
User authentication, profile management, and user-specific data handling.

### `expenses`
Core expense and income tracking with transaction management and serialization.

### `goals`
Financial goal creation and management with built-in feasibility analysis engine.
- Goal priority-based scheduling
- Deadline management
- Multi-goal feasibility checking

### `ai_engine`
Master AI orchestrator with specialized modules:
- **forecast.py**: ML-based savings forecasting
- **feasibility.py**: Goal feasibility analysis and scheduling
- **optimizer.py**: Budget allocation optimization
- **suggestions.py**: Smart financial suggestions
- **overspending.py**: Anomaly detection in spending
- **insights.py**: Financial insights generation
- **strategy.py**: Monthly financial strategy generation
- **clustering.py**: Spending pattern clustering
- **engine.py**: Master AI orchestrator coordinating all modules

### `analytics`
Financial analytics, reporting, and dashboard data generation.

### `groups`
Group management for shared financial goals and collaboration.

### `notifications`
Notification system for alerts, milestones, and important financial events.

## 🚀 Getting Started

### Prerequisites
- Python 3.12+
- pip or conda
- Virtual environment (recommended)
- **Ollama** (for LLM AI features) - [Download Ollama](https://ollama.ai)
- **Llama 3.2 model** (pulled automatically by Ollama)

### Setup Ollama & Llama 3.2

1. **Download and Install Ollama**
   - Visit [https://ollama.ai](https://ollama.ai)
   - Install for your OS (Windows, Mac, Linux)

2. **Pull Llama 3.2 Model**
   ```bash
   ollama pull llama3.2
   ```

3. **Start Ollama Server** (runs in background)
   ```bash
   ollama serve
   ```
   
   Verify it's running at `http://localhost:11434/api/tags`

### Installation

1. **Clone/Extract the project**
   ```bash
   cd ISECO/FINANCE
   ```

2. **Activate the virtual environment**
   ```bash
   # Windows
   broenv\Scripts\activate
   
   # macOS/Linux
   source broenv/bin/activate
   ```

3. **Install dependencies** (if not already installed in venv)
   ```bash
   pip install django djangorestframework numpy scikit-learn scipy
   ```

4. **Apply database migrations**
   ```bash
   cd finance
   python manage.py migrate
   ```

5. **Create a superuser** (for admin access)
   ```bash
   python manage.py createsuperuser
   ```

6. **Run the development server**
   ```bash
   python manage.py runserver
   ```

   The application will be available at `http://localhost:8000/`

### Admin Interface
Access the Django admin panel at `http://localhost:8000/admin/` with your superuser credentials to:
- Manage users
- View and edit expenses
- Manage financial goals
- Configure notifications
- Monitor system activity

## 📡 API Endpoints

All endpoints follow REST principles through Django REST Framework:

| Module | Base URL |
|--------|----------|
| Users | `/users/` |
| Expenses | `/expenses/` |
| Goals | `/goals/` |
| Analytics | `/analytics/` |
| AI Engine | `/ai/` |
| Groups | `/groups/` |
| Notifications | `/notifications/` |

## 🤖 AI Engine Architecture

The AI Engine is a hybrid system combining **Large Language Models (LLM)** and **Machine Learning**:

### LLM Integration: Ollama Llama 3.2
**Advanced conversational AI for financial guidance**
- **Model**: Llama 3.2 (via Ollama framework)
- **Capabilities**:
  - Generates natural language financial advice and explanations
  - Creates context-aware insights from numerical data
  - Provides conversational guidance on financial decisions
  - Explains complex financial scenarios in user-friendly terms
  - Preloaded in memory for instant response times (no cold starts)
- **Host**: localhost:11434 (Ollama server)
- **Optimization**: Model kept in memory permanently with `keep_alive: -1`

### Machine Learning Modules
**Statistical and predictive analysis for financial patterns**

| Module | Purpose | ML Techniques |
|--------|---------|----------------|
| `forecast.py` | Savings & spending prediction | Regression, time-series analysis |
| `feasibility.py` | Goal achievability assessment | Constraint satisfaction, scheduling |
| `optimizer.py` | Budget allocation optimization | Linear programming, priority sorting |
| `clustering.py` | Spending pattern identification | K-means clustering, unsupervised learning |
| `overspending.py` | Anomaly detection | Statistical outlier detection |
| `insights.py` | Pattern extraction | Data mining, aggregation |
| `strategy.py` | Strategic planning | Multi-objective optimization |

### Master AI Output
Unified analysis orchestrating both AI and ML:
- **LLM-Generated Insights**: Conversational explanations of financial situations
- **ML Predictions**: Savings forecasting and spending trends
- **Feasibility Assessment**: Statistical goal analysis with LLM explanations
- **Smart Recommendations**: ML-identified opportunities, LLM-explained
- **Budget Allocation**: Optimized distribution with reasoning
- **Anomaly Alerts**: Detected patterns with natural language summaries
- **Monthly Strategy**: Data-driven recommendations in natural language

### Architecture Benefits
- **User-specific Analysis**: All AI outputs filtered for individual users
- **Error Handling**: Graceful error management throughout both systems
- **Performance Optimization**: Results caching + model preloading for speed
- **Multi-goal Support**: Analyzes multiple goals simultaneously
- **Explainability**: ML decisions explained via LLM for transparency
- **Scalability**: Both LLM and ML components run efficiently

## 📊 Technologies Used

### Core Backend
- **Web Framework**: Django 5.2.8
- **REST API**: Django REST Framework 3.16.1
- **Database**: SQLite3 (development), PostgreSQL (production-ready)

### 🤖 Artificial Intelligence & Machine Learning
**LLM (Large Language Model)**
- **Ollama Framework**: Open-source LLM orchestration
- **Model**: Llama 3.2 (state-of-the-art conversational AI)
- **Use Cases**: Natural language insights, financial guidance, strategy explanation

**ML (Machine Learning)**
- **scikit-learn**: Classification, clustering, optimization algorithms
- **NumPy 2.3.5**: Numerical computing and array operations
- **SciPy 1.16.3**: Scientific computing and statistical analysis
- **Use Cases**: Forecasting, anomaly detection, pattern clustering, feasibility analysis

### Date Handling
- **python-dateutil 2.9.0**: Advanced date manipulation and timezone handling

## 📦 Key Dependencies

### Web & API Framework
| Package | Version | Purpose |
|---------|---------|---------|
| Django | 5.2.8 | Web framework |
| djangorestframework | 3.16.1 | REST API framework |

### 🤖 AI & Machine Learning
| Package | Version | Purpose |
|---------|---------|---------|
| **Ollama** | Latest | LLM orchestration & Llama 3.2 model serving |
| **scikit-learn** | 1.7.2 | Machine learning (clustering, optimization, prediction) |
| **NumPy** | 2.3.5 | Numerical computing & array operations |
| **SciPy** | 1.16.3 | Scientific computing & statistical analysis |

### Utilities
| Package | Version | Purpose |
|---------|---------|---------|
| python-dateutil | 2.9.0 | Date/time utilities |

## 🛠️ Development

### Ensure AI Engine is Ready

Before using AI features, initialize the Ollama engine:

```python
# In your Django views or management commands
from ai_engine.ollama_runner import ensure_ollama_running

ensure_ollama_running()  # Starts Ollama, preloads Llama 3.2, eliminates cold starts
```

### Using the Master AI Engine

```python
from ai_engine.engine import master_ai_output

# Get comprehensive AI analysis for a user
user = User.objects.get(id=1)
ai_analysis = master_ai_output(user=user)

# Returns:
# {
#     'forecast': {...},  # ML-predicted savings
#     'monthly_averages': {...},  # Historical analysis
#     'goal_analysis': [...],  # Goal feasibility + LLM explanations
#     'allocations': {...},  # Optimized budget distribution
#     'suggestions': [...],  # LLM-generated recommendations
#     'overspending': [...],  # ML-detected anomalies + LLM context
#     'insights': {...},  # Pattern analysis + natural language summary
#     'strategy': {...}  # Monthly strategy with reasoning
# }
```

### Database Migrations
```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Revert to previous migration
python manage.py migrate app_name 0001
```

### Running Tests
```bash
python manage.py test
```

### Creating Superuser
```bash
python manage.py createsuperuser
```

## 📝 Configuration

Key settings in [finance/settings.py](finance/finance/settings.py):

- **DEBUG**: Currently set to `True` (change to `False` for production)
- **DATABASE**: SQLite (modify `DATABASES` setting for PostgreSQL)
- **INSTALLED_APPS**: All active apps (users, expenses, goals, ai_engine, etc.)
- **MIDDLEWARE**: Security and session management middleware
- **REST_FRAMEWORK**: DRF configuration for API settings

## ⚠️ Security Notes

- **Development Only**: The SECRET_KEY is exposed - generate a new one for production
- **Debug Mode**: DEBUG is enabled - disable for production deployments
- **CSRF Protection**: Enabled by default - required for POST requests
- **Environment Variables**: Store sensitive settings in environment variables in production

## 📈 Data Models

### User
- Profile and authentication
- Goal targets and preferences

### Expense
- Transaction amount, type (income/expense), category
- Date, description, user reference

### Goal
- Target amount, deadline, priority
- Status (active, completed, abandoned)
- User and group associations

### Notification
- Event type, message, timestamp
- User and group targeting

## 🤝 Contributing

1. Create a new branch for features
2. Make changes in the respective app folders
3. Run migrations if models change
4. Test your changes thoroughly
5. Submit changes for review

## 📄 License

ISECO © 2026. All rights reserved.

## � Troubleshooting AI Features

### Ollama Issues

**Ollama server not running**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not running, start it
ollama serve
```

**Model not found**
```bash
# Verify Llama 3.2 is installed
ollama list

# Pull the model if missing
ollama pull llama3.2
```

**Cold start timeouts**
- The `ensure_ollama_running()` function preloads the model into memory
- Call it once at Django startup to eliminate delays
- Model is kept in memory permanently with `keep_alive: -1`

**Out of Memory (OOM)**
- Llama 3.2 requires significant VRAM
- Ensure your system has 8GB+ available RAM
- Consider running on GPU-enabled hardware for better performance

### ML Pipeline Issues

**Forecasting errors**
- Ensure users have at least 3 months of transaction history
- Check that expense dates are properly formatted

**Goal feasibility always false**
- Verify monthly savings are positive
- Check that goal deadlines are realistic
- Review goal priority rankings

## 💬 Support

For issues, feature requests, or questions about ISECO, please consult the project documentation or contact the development team.

---

**Status**: Active Development | **Last Updated**: April 2026
**AI Model**: Ollama Llama 3.2 | **ML Stack**: scikit-learn, NumPy, SciPy
