package main

import (
	"context"
	"fmt"
	"time"

	openai "github.com/sashabaranov/go-openai"
)

type GPT struct{ 
	cli           *openai.Client
	systemPrompt  string
}

func NewGPT(apiKey, systemPrompt string) (*GPT, error) {
	if apiKey == "" {
		return nil, fmt.Errorf("OpenAI API key is empty")
	}
	return &GPT{
		cli:          openai.NewClient(apiKey),
		systemPrompt: systemPrompt,
	}, nil
}

func (g *GPT) Ask(q string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	
	models := []string{"gpt-5-nano-2025-08-07", "gpt-5-mini-2025-08-07", "gpt-4o-mini"}
	
	for i, model := range models {
		resp, err := g.cli.CreateChatCompletion(ctx, openai.ChatCompletionRequest{
			Model: model,
			Messages: []openai.ChatCompletionMessage{
				{Role: "system", Content: g.systemPrompt},
				{Role: "user", Content: q},
			},
		})
		
		if err == nil {
			if len(resp.Choices) == 0 {
				return "", fmt.Errorf("empty response")
			}
			return resp.Choices[0].Message.Content, nil
		}
		
		if i == len(models)-1 {
			return "", err
		}
		
		time.Sleep(time.Duration(i+1) * 2 * time.Second)
	}
	
	return "", fmt.Errorf("all models failed")
}
