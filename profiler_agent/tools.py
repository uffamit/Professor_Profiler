"""Custom tools for the Professor Profiler agent."""
import os
import json
from typing import Dict, List, Any
from collections import Counter
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

try:
    import pandas as pd
except ImportError:
    pd = None


def read_pdf_content(file_path: str) -> dict:
    """
    Extract text content from a PDF file.
    
    Args:
        file_path: Path to the PDF file
    
    Returns:
        Dictionary with filename and content, or error message
    """
    if PdfReader is None:
        return {"error": "pypdf library is not installed."}
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}
    try:
        reader = PdfReader(file_path)
        text = ""
        page_count = len(reader.pages)
        
        for page_num, page in enumerate(reader.pages, 1):
            page_text = page.extract_text()
            text += f"\n--- Page {page_num} ---\n{page_text}"
        
        return {
            "filename": os.path.basename(file_path),
            "content": text,
            "page_count": page_count,
            "file_path": file_path
        }
    except Exception as e:
        return {"error": f"Failed to read PDF: {str(e)}"}


def analyze_statistics(questions_data: str) -> dict:
    """
    Analyze statistical patterns in exam questions.
    
    Args:
        questions_data: JSON string or dict containing tagged questions
    
    Returns:
        Statistical analysis including frequency distributions
    """
    try:
        # Parse input if it's a string
        if isinstance(questions_data, str):
            data = json.loads(questions_data)
        else:
            data = questions_data
        
        # Extract topics and bloom levels
        topics = []
        bloom_levels = []
        
        if isinstance(data, dict):
            questions = data.get("questions", [])
        elif isinstance(data, list):
            questions = data
        else:
            return {"error": "Invalid input format"}
        
        for q in questions:
            if isinstance(q, dict):
                topics.append(q.get("topic", "Unknown"))
                bloom_levels.append(q.get("bloom_level", "Unknown"))
        
        # Calculate statistics
        topic_freq = Counter(topics)
        bloom_freq = Counter(bloom_levels)
        
        return {
            "total_questions": len(questions),
            "topic_distribution": dict(topic_freq),
            "bloom_distribution": dict(bloom_freq),
            "top_topics": topic_freq.most_common(5),
            "cognitive_complexity": {
                "lower_order": sum(
                    count for level, count in bloom_freq.items()
                    if level.lower() in ["remember", "understand"]
                ),
                "higher_order": sum(
                    count for level, count in bloom_freq.items()
                    if level.lower() in ["apply", "analyze", "evaluate", "create"]
                )
            }
        }
    except Exception as e:
        return {"error": f"Failed to analyze statistics: {str(e)}"}


def visualize_trends(
    statistics: str,
    output_path: str = "trends_chart.png",
    chart_type: str = "bar"
) -> dict:
    """
    Create visualizations for exam trends.
    
    Args:
        statistics: JSON string containing statistical data
        output_path: Path to save the chart
        chart_type: Type of chart ('bar', 'pie', 'line')
    
    Returns:
        Dictionary with chart path and metadata
    """
    if plt is None:
        return {"error": "matplotlib library is not installed"}
    
    try:
        # Parse statistics
        if isinstance(statistics, str):
            stats = json.loads(statistics)
        else:
            stats = statistics
        
        # Create figure with subplots
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        
        # Plot 1: Topic Distribution
        if "topic_distribution" in stats:
            topics = list(stats["topic_distribution"].keys())
            counts = list(stats["topic_distribution"].values())
            
            if chart_type == "bar":
                axes[0].bar(topics, counts, color='skyblue')
                axes[0].set_xlabel('Topics')
                axes[0].set_ylabel('Frequency')
                axes[0].set_title('Topic Distribution')
                axes[0].tick_params(axis='x', rotation=45)
            elif chart_type == "pie":
                axes[0].pie(counts, labels=topics, autopct='%1.1f%%')
                axes[0].set_title('Topic Distribution')
        
        # Plot 2: Bloom's Taxonomy Distribution
        if "bloom_distribution" in stats:
            blooms = list(stats["bloom_distribution"].keys())
            bloom_counts = list(stats["bloom_distribution"].values())
            
            axes[1].bar(blooms, bloom_counts, color='lightcoral')
            axes[1].set_xlabel('Bloom\'s Level')
            axes[1].set_ylabel('Frequency')
            axes[1].set_title('Cognitive Complexity Distribution')
            axes[1].tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        
        # Save figure
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return {
            "chart_path": output_path,
            "chart_type": chart_type,
            "success": True,
            "message": f"Chart saved to {output_path}"
        }
        
    except Exception as e:
        return {"error": f"Failed to create visualization: {str(e)}"}


def compare_exams(exam_files: List[str]) -> dict:
    """
    Compare multiple exam papers to identify trends over time.
    
    Args:
        exam_files: List of PDF file paths to compare
    
    Returns:
        Comparison analysis with trends
    """
    if not exam_files:
        return {"error": "No exam files provided"}
    
    results = []
    
    for file_path in exam_files:
        content = read_pdf_content(file_path)
        if "error" not in content:
            results.append({
                "file": content["filename"],
                "page_count": content.get("page_count", 0),
                "content_length": len(content.get("content", ""))
            })
    
    return {
        "total_exams": len(results),
        "exams_analyzed": results,
        "message": f"Successfully compared {len(results)} exams"
    }