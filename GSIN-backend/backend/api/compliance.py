# backend/api/compliance.py
"""
PHASE 5: Privacy, Terms, and Disclaimer pages.
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_policy():
    """
    Privacy Policy page.
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>GSIN Privacy Policy</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; }
            h1 { color: #333; }
            h2 { color: #555; margin-top: 30px; }
            p { margin: 15px 0; }
            ul { margin: 15px 0; padding-left: 30px; }
        </style>
    </head>
    <body>
        <h1>Privacy Policy</h1>
        <p><strong>Last Updated:</strong> 2024-12-19</p>
        
        <h2>1. Data We Store</h2>
        <p>GSIN stores the following data:</p>
        <ul>
            <li><strong>Account Information:</strong> Email address, name, OAuth provider ID</li>
            <li><strong>Trading Data:</strong> Trade history, strategies, backtest results</li>
            <li><strong>Usage Data:</strong> API usage, feature interactions, preferences</li>
            <li><strong>MCN Data:</strong> Anonymized embeddings for AI learning (no personal identifiers)</li>
        </ul>
        
        <h2>2. Data We Do NOT Store</h2>
        <ul>
            <li><strong>Passwords:</strong> Passwords are hashed and never stored in plain text</li>
            <li><strong>Banking Information:</strong> We do not store credit card numbers or bank account details</li>
            <li><strong>Personal Identifiers in MCN:</strong> MCN embeddings are anonymized and do not contain personal information</li>
        </ul>
        
        <h2>3. MCN (Memory Cluster Networks) Data</h2>
        <p>Our AI system uses anonymized embeddings to learn from trading patterns. These embeddings:</p>
        <ul>
            <li>Do not contain personal identifiers</li>
            <li>Are used for pattern recognition and strategy improvement</li>
            <li>Cannot be reverse-engineered to identify individual users</li>
        </ul>
        
        <h2>4. Your Rights</h2>
        <ul>
            <li><strong>Right to Access:</strong> You can access all your data through the API</li>
            <li><strong>Right to Delete:</strong> You can delete your account and all associated data</li>
            <li><strong>Right to Export:</strong> You can export your trading data at any time</li>
        </ul>
        
        <h2>5. Data Security</h2>
        <p>We use industry-standard security measures including encryption, secure authentication (JWT), and regular security audits.</p>
        
        <h2>6. Contact</h2>
        <p>For privacy concerns, contact: privacy@gsin.fin</p>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@router.get("/terms", response_class=HTMLResponse)
async def terms_of_service():
    """
    Terms of Service page.
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>GSIN Terms of Service</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; }
            h1 { color: #333; }
            h2 { color: #555; margin-top: 30px; }
            p { margin: 15px 0; }
            ul { margin: 15px 0; padding-left: 30px; }
        </style>
    </head>
    <body>
        <h1>Terms of Service</h1>
        <p><strong>Last Updated:</strong> 2024-12-19</p>
        
        <h2>1. Acceptance of Terms</h2>
        <p>By using GSIN, you agree to these terms of service.</p>
        
        <h2>2. Platform Description</h2>
        <p>GSIN is an AI-powered trading strategy platform that provides:</p>
        <ul>
            <li>Paper trading capabilities</li>
            <li>Strategy backtesting and evolution</li>
            <li>AI-enhanced trading signals</li>
            <li>Strategy marketplace and royalties</li>
        </ul>
        
        <h2>3. User Responsibilities</h2>
        <ul>
            <li>You are responsible for all trades executed using your account</li>
            <li>You must comply with all applicable laws and regulations</li>
            <li>You must not use the platform for illegal activities</li>
            <li>You are responsible for maintaining account security</li>
        </ul>
        
        <h2>4. Royalties and Payments</h2>
        <ul>
            <li>Strategy creators receive royalties when their strategies generate profit</li>
            <li>Royalty rates: 3% for CREATOR tier, 5% for regular users</li>
            <li>GSIN retains a platform fee (5%) from royalties</li>
            <li>All payments are processed securely through Stripe</li>
        </ul>
        
        <h2>5. Intellectual Property</h2>
        <p>Strategies uploaded to GSIN remain the property of their creators. By uploading, you grant GSIN a license to use, backtest, and evolve your strategies.</p>
        
        <h2>6. Limitation of Liability</h2>
        <p>GSIN is provided "as is" without warranties. We are not liable for trading losses or strategy performance.</p>
        
        <h2>7. Contact</h2>
        <p>For questions about these terms, contact: support@gsin.fin</p>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@router.get("/disclaimer", response_class=HTMLResponse)
async def trading_disclaimer():
    """
    Trading Disclaimer page.
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>GSIN Trading Disclaimer</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; }
            h1 { color: #d32f2f; }
            h2 { color: #555; margin-top: 30px; }
            p { margin: 15px 0; }
            ul { margin: 15px 0; padding-left: 30px; }
            .warning { background-color: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0; }
        </style>
    </head>
    <body>
        <h1>⚠️ Trading Disclaimer</h1>
        <p><strong>Last Updated:</strong> 2024-12-19</p>
        
        <div class="warning">
            <strong>IMPORTANT:</strong> Trading involves substantial risk of loss. Past performance does not guarantee future results.
        </div>
        
        <h2>1. Risks of Trading</h2>
        <ul>
            <li><strong>Financial Loss:</strong> You may lose all or more than your initial investment</li>
            <li><strong>Market Volatility:</strong> Markets can be highly volatile and unpredictable</li>
            <li><strong>Strategy Performance:</strong> No strategy guarantees profits</li>
            <li><strong>Leverage Risk:</strong> Leveraged trading can amplify losses</li>
            <li><strong>Technical Failures:</strong> System failures may result in losses</li>
        </ul>
        
        <h2>2. GSIN Responsibility Limits</h2>
        <ul>
            <li>GSIN provides tools and signals, but does not guarantee trading outcomes</li>
            <li>All trading decisions are your own responsibility</li>
            <li>GSIN is not a financial advisor</li>
            <li>AI signals are suggestions, not financial advice</li>
            <li>GSIN is not liable for trading losses</li>
        </ul>
        
        <h2>3. Paper Trading vs Real Trading</h2>
        <ul>
            <li><strong>Paper Trading:</strong> Risk-free simulation using virtual funds</li>
            <li><strong>Real Trading:</strong> Uses real money and involves real risk</li>
            <li>Always test strategies in paper mode before real trading</li>
            <li>Never trade with money you cannot afford to lose</li>
        </ul>
        
        <h2>4. AI and Strategy Limitations</h2>
        <ul>
            <li>AI signals are based on historical data and patterns</li>
            <li>Past performance does not predict future results</li>
            <li>Market conditions can change rapidly</li>
            <li>Strategies may become ineffective over time</li>
        </ul>
        
        <h2>5. Regulatory Compliance</h2>
        <p>You are responsible for ensuring your trading activities comply with all applicable laws and regulations in your jurisdiction.</p>
        
        <h2>6. No Investment Advice</h2>
        <p>GSIN does not provide investment, financial, or trading advice. All information is for educational and informational purposes only.</p>
        
        <h2>7. Acknowledgment</h2>
        <p>By using GSIN, you acknowledge that you understand and accept these risks and limitations.</p>
        
        <h2>8. Contact</h2>
        <p>For questions about this disclaimer, contact: support@gsin.fin</p>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

