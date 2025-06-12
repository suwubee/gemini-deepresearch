"""
Prompt Templates for DeepSearch Research Engine
Based on original backend prompts structure
"""

from datetime import datetime
from typing import Dict, List


def get_current_date():
    """Get current date in a readable format"""
    return datetime.now().strftime("%B %d, %Y")


class PromptTemplates:
    """Prompt template management class"""
    
    @staticmethod
    def task_analysis_prompt(user_query: str) -> str:
        """Task analysis prompt"""
        current_date = get_current_date()
        
        return f"""You are a professional task analysis expert. Analyze the user's query and determine the most suitable task type and workflow.

Current date: {current_date}
User query: {user_query}

Instructions:
- Analyze the query to determine if it needs deep research, simple Q&A, coding help, data analysis, or document writing
- Consider complexity and time requirements
- Generate appropriate workflow steps

Output Format:
- Format your response as a JSON object with these exact keys:

Example:
```json
{{
    "task_type": "Deep Research",
    "complexity": "Medium",
    "requires_search": true,
    "requires_multiple_rounds": true,
    "estimated_steps": 5,
    "estimated_time": "3-8 minutes",
    "reasoning": "Query requires comprehensive research and analysis of current trends"
}}
```

Task Types:
- "Deep Research": For trends, analysis, market research, detailed studies
- "Q&A System": For simple, direct questions  
- "Code Generation": For programming help and technical implementation
- "Data Analysis": For data processing and statistical analysis
- "Document Writing": For creating reports and documents
- "Comprehensive Task": For complex multi-faceted requests

Context: {user_query}"""

    @staticmethod
    def search_query_generation_prompt(user_query: str, iteration: int = 1) -> str:
        """Search query generation prompt"""
        current_date = get_current_date()
        
        query_writer_instructions = f"""Your goal is to generate sophisticated and diverse web search queries for comprehensive research on the given topic.

Instructions:
- Generate 3 diverse search queries that focus on different aspects of the topic
- Each query should be specific and targeted
- Queries should ensure current information is gathered. The current date is {current_date}
- Use English for better search results
- Don't generate duplicate or overly similar queries

Format: 
- Format your response as a JSON object with these exact keys:
   - "rationale": Brief explanation of why these queries cover the topic comprehensively
   - "query": A list of 3 search queries

Example:

Topic: AI trends 2025 analysis
```json
{{
    "rationale": "These queries target different aspects: market data and forecasts, specific technology developments, and industry impact analysis to provide comprehensive coverage of AI trends.",
    "query": ["AI market size growth forecast 2025", "emerging AI technologies 2025", "AI industry impact trends 2025"]
}}
```

Context: {user_query}"""
        
        return query_writer_instructions

    @staticmethod  
    def reflection_prompt(user_query: str, search_results: List[str]) -> str:
        """Reflection analysis prompt"""
        results_text = "\n\n---\n\n".join(search_results)
        current_date = get_current_date()
        
        reflection_instructions = f"""You are an expert research assistant analyzing search results about "{user_query}".

Instructions:
- Identify knowledge gaps or areas that need deeper exploration
- If summaries are sufficient to answer the user's question, don't generate follow-up queries
- If there are knowledge gaps, generate specific follow-up queries
- Focus on missing details, emerging trends, or technical specifics not fully covered

Requirements:
- Ensure follow-up queries are self-contained and include necessary context for web search

Output Format:
- Format your response as a JSON object with these exact keys:
   - "is_sufficient": true or false
   - "knowledge_gap": Describe what information is missing or needs clarification
   - "follow_up_queries": Write specific questions to address gaps

Example:
```json
{{
    "is_sufficient": false,
    "knowledge_gap": "Missing specific market size data and growth projections for 2025",
    "follow_up_queries": ["AI market size forecast 2025 specific numbers", "AI growth rate projections 2025 statistics"]
}}
```

Summaries:
{results_text}"""
        
        return reflection_instructions

    @staticmethod
    def answer_synthesis_prompt(user_query: str, all_search_results: List[str]) -> str:
        """Answer synthesis prompt"""
        results_text = "\n\n---\n\n".join(all_search_results)
        current_date = get_current_date()
        
        answer_instructions = f"""Generate a high-quality answer to the user's question based on the provided search results.

Instructions:
- The current date is {current_date}
- Generate a comprehensive answer based on the search results
- **CRITICAL**: When you mention information from the search results, you MUST insert inline citations using markdown link format: [source_name](url)
- Parse the "Citations:" sections from each summary and use those exact URLs for linking
- Detect the language of the user's question and respond in the SAME language
- Structure the answer clearly with appropriate sections and formatting

Citation Format Examples:
- Instead of writing "AI market will grow", write "AI market will grow [bondcap](https://bondcap.com/article-url)"
- Instead of writing "according to research", write "according to research [zdnet](https://zdnet.com/article-url)"

User Context:
- {user_query}

Search Results with Citations:
{results_text}

Remember: Every factual claim should include a clickable citation link in [text](url) format using the URLs provided in the Citations sections."""
        
        return answer_instructions

    @staticmethod
    def code_generation_prompt(user_query: str, context: str = "") -> str:
        """Code generation prompt"""
        return f"""You are a professional software development expert. Please generate high-quality code for user requirements.

User requirements: {user_query}
Context information: {context}

Please provide:
1. Complete code implementation
2. Detailed comments
3. Usage examples
4. Possible improvement suggestions

Code requirements:
- Follow best practices
- Include error handling
- High code readability
- Performance optimization
"""

    @staticmethod
    def data_analysis_prompt(user_query: str, data_info: str = "") -> str:
        """Data analysis prompt"""
        return f"""You are a professional data analyst. Please provide a detailed analysis plan for the user's data analysis requirements.

Analysis requirements: {user_query}
Data information: {data_info}

Please provide:
1. Analysis approach and methods
2. Specific analysis steps
3. Visualization recommendations
4. Conclusions and insights

Analysis requirements:
- Scientifically rigorous methods
- Well-founded conclusions
- Clear visualization
- Strong practicality
""" 