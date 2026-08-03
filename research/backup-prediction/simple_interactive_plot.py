#!/usr/bin/env python3

import pandas as pd
import json

def create_simple_interactive_plot():
    """Create a simple interactive plot using vanilla HTML/CSS/JS"""

    # Load the data
    try:
        df = pd.read_csv('rb_efficiency_vs_oline_2025.csv')
    except FileNotFoundError:
        print("Error: 'rb_efficiency_vs_oline_2025.csv' not found.")
        return

    # Filter to RBs with meaningful data
    df_clean = df[
        (df['team_pct_positive_plays'].notna()) &
        (df['total_touches'] >= 20)
    ].copy()

    print(f'Creating simple interactive plot for {len(df_clean)} RBs')

    # Prepare data for JavaScript
    players = []
    for _, row in df_clean.iterrows():
        players.append({
            'name': row['player_name'],
            'team': row['team'],
            'x': float(row['team_pct_positive_plays']),
            'y': int(row['total_touches']),
            'efficiency': float(row['pct_of_expected']),
            'points_over_expected': float(row.get('points_over_expected', 0)),
            'fantasy_points': float(row.get('actual_fantasy_points', 0))
        })

    # Create HTML content
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>RB Efficiency vs O-Line Quality</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        h1 {{
            text-align: center;
            color: #333;
            margin-bottom: 30px;
        }}

        .search-container {{
            margin-bottom: 20px;
            text-align: center;
            position: relative;
            display: inline-block;
        }}

        #search-input {{
            width: 400px;
            padding: 10px;
            font-size: 16px;
            border: 2px solid #ddd;
            border-radius: 4px;
        }}

        #search-results {{
            position: absolute;
            top: 100%;
            left: 0;
            width: 400px;
            max-height: 200px;
            overflow-y: auto;
            background: white;
            border: 1px solid #ddd;
            border-top: none;
            display: none;
            z-index: 1000;
        }}

        .search-result-item {{
            padding: 8px;
            cursor: pointer;
            border-bottom: 1px solid #eee;
        }}

        .search-result-item:hover {{
            background-color: #f0f0f0;
        }}

        .search-result-item.highlighted {{
            background-color: #e6f3ff;
        }}

        #clear-btn {{
            margin-left: 10px;
            padding: 10px 20px;
            background-color: #ff4444;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }}

        #clear-btn:hover {{
            background-color: #cc0000;
        }}

        .chart-container {{
            position: relative;
            width: 100%;
            height: 600px;
            border: 1px solid #ddd;
            margin: 20px 0;
        }}

        #chart {{
            width: 100%;
            height: 100%;
        }}

        .tooltip {{
            position: absolute;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 8px;
            border-radius: 4px;
            font-size: 12px;
            pointer-events: none;
            z-index: 1000;
            display: none;
        }}

        .stats {{
            text-align: center;
            margin-top: 20px;
            padding: 15px;
            background: #f9f9f9;
            border-radius: 4px;
        }}

        .team-filter-container {{
            margin: 20px 0;
            padding: 15px;
            background: #f8f8f8;
            border-radius: 4px;
            border: 1px solid #ddd;
        }}

        .team-filter-title {{
            font-weight: bold;
            margin-bottom: 10px;
            color: #333;
        }}

        .team-buttons {{
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
            margin-bottom: 10px;
        }}

        .team-btn {{
            padding: 6px 10px;
            font-size: 12px;
            font-weight: bold;
            color: white;
            background-color: #666;
            border: none;
            border-radius: 3px;
            cursor: pointer;
            transition: all 0.2s;
            min-width: 45px;
        }}

        .team-btn:hover {{
            background-color: #555;
            transform: translateY(-1px);
        }}

        .team-btn.selected {{
            background-color: #007bff;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }}

        .filter-controls {{
            margin-top: 10px;
        }}

        .clear-filters-btn {{
            padding: 8px 16px;
            background-color: #dc3545;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }}

        .clear-filters-btn:hover {{
            background-color: #c82333;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>RB Touches vs Team O-Line Quality</h1>

        <div class="search-container">
            <input type="text" id="search-input" placeholder="Search for a player (e.g., 'Gibbs', 'Henry', 'Barkley')..." autocomplete="off" spellcheck="false">
            <div id="search-results"></div>
            <button id="clear-btn">Clear</button>
        </div>

        <div class="team-filter-container">
            <div class="team-filter-title">Filter by Team:</div>
            <div class="team-buttons" id="team-buttons">
                <!-- Team buttons will be generated by JavaScript -->
            </div>
            <div class="filter-controls">
                <button class="clear-filters-btn" id="clear-filters-btn">Clear All Filters</button>
            </div>
        </div>

        <div class="chart-container">
            <svg id="chart"></svg>
            <div class="tooltip" id="tooltip"></div>
        </div>

        <div class="stats" id="stats"></div>
    </div>

    <script>
        // Data
        const players = {json.dumps(players, indent=8)};

        // Chart dimensions
        const margin = {{top: 20, right: 150, bottom: 80, left: 100}};
        const width = 1000 - margin.left - margin.right;
        const height = 500 - margin.top - margin.bottom;

        // Create SVG
        const svg = document.getElementById('chart');
        svg.setAttribute('width', width + margin.left + margin.right);
        svg.setAttribute('height', height + margin.top + margin.bottom);

        // Create chart group
        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.setAttribute('transform', `translate(${{margin.left}},${{margin.top}})`);
        svg.appendChild(g);

        // Calculate scales
        const xValues = players.map(p => p.x);
        const yValues = players.map(p => p.y);
        const efficiencyValues = players.map(p => p.efficiency);

        const xMin = Math.min(...xValues);
        const xMax = Math.max(...xValues);
        const yMin = Math.min(...yValues);
        const yMax = Math.max(...yValues);
        const efficiencyMin = Math.min(...efficiencyValues);
        const efficiencyMax = Math.max(...efficiencyValues);

        // Scale functions
        const xScale = (value) => ((value - xMin) / (xMax - xMin)) * width;
        const yScale = (value) => height - ((value - yMin) / (yMax - yMin)) * height;
        const sizeScale = (efficiency) => 3 + ((efficiency - efficiencyMin) / (efficiencyMax - efficiencyMin)) * 12;
        const colorScale = (efficiency) => {{
            // Use absolute efficiency thresholds instead of normalized
            if (efficiency < 80) {{
                // Below 80%: Red
                return `hsl(0, 90%, 45%)`;
            }} else if (efficiency < 90) {{
                // 80-90%: Orange-red
                return `hsl(15, 90%, 50%)`;
            }} else if (efficiency < 100) {{
                // 90-100%: Orange
                return `hsl(35, 90%, 55%)`;
            }} else if (efficiency < 110) {{
                // 100-110%: Yellow-green
                return `hsl(70, 85%, 50%)`;
            }} else if (efficiency < 120) {{
                // 110-120%: Light green
                return `hsl(100, 80%, 45%)`;
            }} else {{
                // Above 120%: Dark green
                return `hsl(120, 85%, 40%)`;
            }}
        }};

        // Draw axes
        function drawAxes() {{
            // X axis
            const xAxis = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            xAxis.setAttribute('x1', 0);
            xAxis.setAttribute('y1', height);
            xAxis.setAttribute('x2', width);
            xAxis.setAttribute('y2', height);
            xAxis.setAttribute('stroke', '#333');
            xAxis.setAttribute('stroke-width', 2);
            g.appendChild(xAxis);

            // Y axis
            const yAxis = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            yAxis.setAttribute('x1', 0);
            yAxis.setAttribute('y1', 0);
            yAxis.setAttribute('x2', 0);
            yAxis.setAttribute('y2', height);
            yAxis.setAttribute('stroke', '#333');
            yAxis.setAttribute('stroke-width', 2);
            g.appendChild(yAxis);

            // X axis label
            const xLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            xLabel.setAttribute('x', width / 2);
            xLabel.setAttribute('y', height + 50);
            xLabel.setAttribute('text-anchor', 'middle');
            xLabel.setAttribute('font-size', '16');
            xLabel.setAttribute('font-weight', 'bold');
            xLabel.setAttribute('fill', '#333');
            xLabel.textContent = 'Team O-Line % Positive Plays (2024)';
            g.appendChild(xLabel);

            // Y axis label
            const yLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            yLabel.setAttribute('x', -70);
            yLabel.setAttribute('y', height / 2);
            yLabel.setAttribute('text-anchor', 'middle');
            yLabel.setAttribute('font-size', '16');
            yLabel.setAttribute('font-weight', 'bold');
            yLabel.setAttribute('fill', '#333');
            yLabel.setAttribute('transform', `rotate(-90, -70, ${{height / 2}})`);
            yLabel.textContent = 'Total Touches (2024)';
            g.appendChild(yLabel);

            // X axis ticks
            for (let i = 0; i <= 5; i++) {{
                const value = xMin + (xMax - xMin) * (i / 5);
                const x = xScale(value);

                const tick = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                tick.setAttribute('x1', x);
                tick.setAttribute('y1', height);
                tick.setAttribute('x2', x);
                tick.setAttribute('y2', height + 5);
                tick.setAttribute('stroke', '#333');
                g.appendChild(tick);

                const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                label.setAttribute('x', x);
                label.setAttribute('y', height + 18);
                label.setAttribute('text-anchor', 'middle');
                label.setAttribute('font-size', '12');
                label.setAttribute('fill', '#333');
                label.textContent = value.toFixed(1);
                g.appendChild(label);
            }}

            // Y axis ticks
            for (let i = 0; i <= 5; i++) {{
                const value = yMin + (yMax - yMin) * (i / 5);
                const y = yScale(value);

                const tick = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                tick.setAttribute('x1', -5);
                tick.setAttribute('y1', y);
                tick.setAttribute('x2', 0);
                tick.setAttribute('y2', y);
                tick.setAttribute('stroke', '#333');
                g.appendChild(tick);

                const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                label.setAttribute('x', -10);
                label.setAttribute('y', y + 4);
                label.setAttribute('text-anchor', 'end');
                label.setAttribute('font-size', '12');
                label.setAttribute('fill', '#333');
                label.textContent = Math.round(value);
                g.appendChild(label);
            }}
        }}

        // Draw trend line
        function drawTrendLine() {{
            // Simple linear regression
            const n = players.length;
            const sumX = players.reduce((sum, p) => sum + p.x, 0);
            const sumY = players.reduce((sum, p) => sum + p.y, 0);
            const sumXY = players.reduce((sum, p) => sum + p.x * p.y, 0);
            const sumXX = players.reduce((sum, p) => sum + p.x * p.x, 0);

            const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
            const intercept = (sumY - slope * sumX) / n;

            const x1 = xMin;
            const y1 = slope * x1 + intercept;
            const x2 = xMax;
            const y2 = slope * x2 + intercept;

            const trendLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            trendLine.setAttribute('x1', xScale(x1));
            trendLine.setAttribute('y1', yScale(y1));
            trendLine.setAttribute('x2', xScale(x2));
            trendLine.setAttribute('y2', yScale(y2));
            trendLine.setAttribute('stroke', '#ff0000');
            trendLine.setAttribute('stroke-width', 2);
            trendLine.setAttribute('stroke-dasharray', '5,5');
            g.appendChild(trendLine);

            // Calculate correlation
            const correlation = calculateCorrelation();
            document.getElementById('stats').innerHTML = `
                <strong>Statistics:</strong>
                Slope: ${{slope.toFixed(3)}} |
                Correlation: ${{correlation.toFixed(3)}} |
                R²: ${{(correlation * correlation).toFixed(3)}} |
                Players: ${{n}}
            `;
        }}

        // Calculate correlation coefficient
        function calculateCorrelation() {{
            const n = players.length;
            const sumX = players.reduce((sum, p) => sum + p.x, 0);
            const sumY = players.reduce((sum, p) => sum + p.y, 0);
            const sumXY = players.reduce((sum, p) => sum + p.x * p.y, 0);
            const sumXX = players.reduce((sum, p) => sum + p.x * p.x, 0);
            const sumYY = players.reduce((sum, p) => sum + p.y * p.y, 0);

            const numerator = n * sumXY - sumX * sumY;
            const denominator = Math.sqrt((n * sumXX - sumX * sumX) * (n * sumYY - sumY * sumY));

            return numerator / denominator;
        }}

        // Team filtering variables
        let selectedTeams = new Set();
        let allCircles = [];

        // Draw points
        let highlightedPlayer = null;

        function drawPoints() {{
            players.forEach((player, index) => {{
                const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                circle.setAttribute('cx', xScale(player.x));
                circle.setAttribute('cy', yScale(player.y));
                circle.setAttribute('r', sizeScale(player.efficiency));
                circle.setAttribute('fill', colorScale(player.efficiency));
                circle.setAttribute('stroke', '#333');
                circle.setAttribute('stroke-width', 1);
                circle.setAttribute('opacity', 0.7);
                circle.setAttribute('data-index', index);
                circle.setAttribute('data-team', player.team);
                circle.style.cursor = 'pointer';

                // Add hover events
                circle.addEventListener('mouseenter', (e) => showTooltip(e, player));
                circle.addEventListener('mouseleave', hideTooltip);
                circle.addEventListener('click', () => highlightPlayer(player, circle));

                g.appendChild(circle);
                allCircles.push({{ circle, player, index }});
            }});
        }}

        // Draw color legend
        function drawColorLegend() {{
            const legendX = width + 20;
            const legendY = 50;
            const legendHeight = 200;
            const legendWidth = 20;

            // Create legend title
            const legendTitle = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            legendTitle.setAttribute('x', legendX + legendWidth / 2);
            legendTitle.setAttribute('y', legendY - 10);
            legendTitle.setAttribute('text-anchor', 'middle');
            legendTitle.setAttribute('font-size', '12');
            legendTitle.setAttribute('font-weight', 'bold');
            legendTitle.textContent = 'Efficiency %';
            g.appendChild(legendTitle);

            // Create gradient for legend
            const gradient = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
            const linearGradient = document.createElementNS('http://www.w3.org/2000/svg', 'linearGradient');
            linearGradient.setAttribute('id', 'legend-gradient');
            linearGradient.setAttribute('x1', '0%');
            linearGradient.setAttribute('y1', '100%');
            linearGradient.setAttribute('x2', '0%');
            linearGradient.setAttribute('y2', '0%');

            // Add color stops to match the absolute efficiency thresholds
            const colorStops = [
                {{ offset: 0, color: 'hsl(0, 90%, 45%)' }},     // <80%: Red
                {{ offset: 16.7, color: 'hsl(15, 90%, 50%)' }}, // 80-90%: Orange-red
                {{ offset: 33.3, color: 'hsl(35, 90%, 55%)' }}, // 90-100%: Orange
                {{ offset: 50, color: 'hsl(70, 85%, 50%)' }},   // 100-110%: Yellow-green
                {{ offset: 66.7, color: 'hsl(100, 80%, 45%)' }}, // 110-120%: Light green
                {{ offset: 83.3, color: 'hsl(120, 85%, 40%)' }}, // >120%: Dark green
                {{ offset: 100, color: 'hsl(120, 85%, 40%)' }}   // >120%: Dark green
            ];

            colorStops.forEach(stopData => {{
                const stop = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
                stop.setAttribute('offset', stopData.offset + '%');
                stop.setAttribute('stop-color', stopData.color);
                linearGradient.appendChild(stop);
            }});

            gradient.appendChild(linearGradient);
            svg.appendChild(gradient);

            // Create legend rectangle
            const legendRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            legendRect.setAttribute('x', legendX);
            legendRect.setAttribute('y', legendY);
            legendRect.setAttribute('width', legendWidth);
            legendRect.setAttribute('height', legendHeight);
            legendRect.setAttribute('fill', 'url(#legend-gradient)');
            legendRect.setAttribute('stroke', '#333');
            legendRect.setAttribute('stroke-width', 1);
            g.appendChild(legendRect);

            // Add legend labels with meaningful thresholds
            const thresholds = [80, 90, 100, 110, 120];
            const labels = ['<80%', '80%', '90%', '100%', '110%', '120%', '>120%'];

            for (let i = 0; i < labels.length; i++) {{
                const y = legendY + legendHeight - (legendHeight * (i / (labels.length - 1)));

                const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                label.setAttribute('x', legendX + legendWidth + 5);
                label.setAttribute('y', y + 4);
                label.setAttribute('font-size', '10');
                label.textContent = labels[i];
                g.appendChild(label);
            }}
        }}

        // Tooltip functions
        function showTooltip(e, player) {{
            const tooltip = document.getElementById('tooltip');
            tooltip.innerHTML = `
                <strong>${{player.name}} (${{player.team}})</strong><br>
                O-Line: ${{player.x.toFixed(1)}}%<br>
                Touches: ${{player.y}}<br>
                Efficiency: ${{player.efficiency.toFixed(1)}}%<br>
                Points Over Expected: ${{player.points_over_expected.toFixed(1)}}<br>
                Fantasy Points: ${{player.fantasy_points.toFixed(1)}}
            `;
            tooltip.style.display = 'block';

            // Get the chart container's position
            const chartContainer = document.querySelector('.chart-container');
            const containerRect = chartContainer.getBoundingClientRect();

            // Position tooltip relative to the chart container
            const relativeX = e.clientX - containerRect.left;
            const relativeY = e.clientY - containerRect.top;

            tooltip.style.left = (relativeX + 15) + 'px';
            tooltip.style.top = (relativeY - 5) + 'px';
        }}

        function hideTooltip() {{
            document.getElementById('tooltip').style.display = 'none';
        }}

        // Highlight player
        function highlightPlayer(player, circle) {{
            // Reset previous highlight
            if (highlightedPlayer) {{
                highlightedPlayer.setAttribute('stroke-width', 1);
                highlightedPlayer.setAttribute('stroke', '#333');
            }}

            // Highlight new player
            circle.setAttribute('stroke-width', 3);
            circle.setAttribute('stroke', '#ff0000');
            highlightedPlayer = circle;

            // Update search input
            document.getElementById('search-input').value = `${{player.name}} (${{player.team}})`;
        }}

        // Search functionality
        const searchInput = document.getElementById('search-input');
        const searchResults = document.getElementById('search-results');

        // Simple fuzzy matching function
        function fuzzyMatch(pattern, str) {{
            pattern = pattern.toLowerCase();
            str = str.toLowerCase();

            if (str.includes(pattern)) {{
                return str.indexOf(pattern) === 0 ? 100 : 90;
            }}

            let score = 0;
            let patternIdx = 0;

            for (let i = 0; i < str.length && patternIdx < pattern.length; i++) {{
                if (str[i] === pattern[patternIdx]) {{
                    score += 1;
                    patternIdx++;
                }}
            }}

            return patternIdx === pattern.length ? score : 0;
        }}

        function searchPlayers(query) {{
            if (!query.trim()) {{
                searchResults.style.display = 'none';
                return;
            }}

            const matches = players
                .map((player, index) => ({{
                    player,
                    index,
                    score: fuzzyMatch(query, `${{player.name}} (${{player.team}})`)
                }}))
                .filter(item => item.score > 0)
                .sort((a, b) => b.score - a.score)
                .slice(0, 10);

            if (matches.length > 0) {{
                searchResults.innerHTML = matches
                    .map(item =>
                        `<div class="search-result-item" onclick="highlightPlayerByIndex(${{item.index}})">
                            ${{item.player.name}} (${{item.player.team}})
                        </div>`
                    ).join('');
                searchResults.style.display = 'block';
            }} else {{
                searchResults.style.display = 'none';
            }}
        }}

        function highlightPlayerByIndex(playerIndex) {{
            const player = players[playerIndex];
            const circles = g.querySelectorAll('circle');

            if (circles[playerIndex]) {{
                highlightPlayer(player, circles[playerIndex]);
            }}

            searchResults.style.display = 'none';
            searchInput.value = `${{player.name}} (${{player.team}})`;
        }}

        function clearHighlight() {{
            if (highlightedPlayer) {{
                highlightedPlayer.setAttribute('stroke-width', 1);
                highlightedPlayer.setAttribute('stroke', '#333');
                highlightedPlayer = null;
            }}
            searchInput.value = '';
            searchResults.style.display = 'none';
        }}

        // Event listeners
        searchInput.addEventListener('input', (e) => {{
            searchPlayers(e.target.value);
        }});

        document.addEventListener('click', (e) => {{
            if (!e.target.closest('.search-container')) {{
                searchResults.style.display = 'none';
            }}
        }});

        searchInput.addEventListener('keydown', (e) => {{
            if (e.key === 'Enter') {{
                e.preventDefault();
                const firstResult = searchResults.querySelector('.search-result-item');
                if (firstResult) {{
                    firstResult.click();
                }}
            }}
        }});

        document.getElementById('clear-btn').addEventListener('click', clearHighlight);

        // Team filtering functionality
        function createTeamButtons() {{
            const teams = [...new Set(players.map(p => p.team))].sort();
            const teamButtonsContainer = document.getElementById('team-buttons');

            teams.forEach(team => {{
                const button = document.createElement('button');
                button.className = 'team-btn';
                button.textContent = team;
                button.onclick = () => toggleTeamFilter(team, button);
                teamButtonsContainer.appendChild(button);
            }});
        }}

        function toggleTeamFilter(team, button) {{
            if (selectedTeams.has(team)) {{
                selectedTeams.delete(team);
                button.classList.remove('selected');
            }} else {{
                selectedTeams.add(team);
                button.classList.add('selected');
            }}
            applyTeamFilters();
        }}

        function applyTeamFilters() {{
            allCircles.forEach(item => {{
                const {{ circle, player }} = item;
                if (selectedTeams.size === 0 || selectedTeams.has(player.team)) {{
                    circle.style.display = 'block';
                    circle.setAttribute('opacity', 0.7);
                }} else {{
                    circle.style.display = 'none';
                }}
            }});
        }}

        function clearAllFilters() {{
            selectedTeams.clear();
            document.querySelectorAll('.team-btn').forEach(btn => {{
                btn.classList.remove('selected');
            }});
            applyTeamFilters();
        }}

        document.getElementById('clear-filters-btn').addEventListener('click', clearAllFilters);

        // Initialize chart
        drawAxes();
        drawTrendLine();
        drawPoints();
        drawColorLegend();
        createTeamButtons();
    </script>
</body>
</html>
"""

    # Save the HTML file
    filename = 'simple_rb_plot.html'
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Saved simple interactive plot to: {filename}")
    return df_clean

if __name__ == "__main__":
    create_simple_interactive_plot()