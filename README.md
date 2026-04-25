# ISECO - Intelligent Smart Expense & Goal Companion

An advanced Django-based financial management system powered by AI, designed to help users track expenses, manage financial goals, optimize spending, and make data-driven financial decisions.

## 🌟 Key Features

### Expense Management
- Track income and expenses with detailed categorization
- Real-time expense monitoring and analysis
- Flexible filtering and search capabilities
- Transaction history and reporting

### AI-Powered Financial Intelligence
- **Smart Forecasting**: ML-based predictions of future savings and spending patterns
- **Goal Feasibility Analysis**: Intelligent analysis of whether financial goals are achievable
- **Spending Optimization**: Priority-based budget allocation across multiple goals
- **Overspending Detection**: Automatic alerts for spending anomalies
- **Smart Suggestions**: Personalized recommendations for spending improvements
- **Spending Clustering**: Categorize and identify spending patterns through machine learning
- **Monthly Strategy Generation**: AI-generated monthly financial strategies

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

## 🤖 AI Engine Capabilities

The AI Engine provides intelligent financial analysis:

### Master AI Output
Combined analysis across all AI modules:
- Savings forecasting
- Goal feasibility assessment
- Budget allocation
- Spending insights
- Overspending alerts
- Smart suggestions
- Monthly strategies

### Key Features
- **User-specific Analysis**: All AI outputs are filtered for individual users
- **Error Handling**: Graceful error management throughout
- **Performance Optimization**: Results caching to prevent redundant computation
- **Multi-goal Support**: Analyzes multiple goals simultaneously

## 📊 Technologies Used

- **Backend**: Django 5.2.8
- **API**: Django REST Framework 3.16.1
- **Machine Learning**: scikit-learn, NumPy, SciPy
- **Database**: SQLite3 (development), supports PostgreSQL for production
- **Environment Management**: Python venv

## 📦 Key Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| Django | 5.2.8 | Web framework |
| djangorestframework | 3.16.1 | REST API |
| numpy | 2.3.5 | Numerical computing |
| scikit-learn | 1.7.2 | Machine learning |
| scipy | 1.16.3 | Scientific computing |
| python-dateutil | 2.9.0 | Date utilities |

## 🛠️ Development

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

## 💬 Support

For issues, feature requests, or questions about ISECO, please consult the project documentation or contact the development team.

---

**Status**: Active Development | **Last Updated**: April 2026
