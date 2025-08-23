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
	// Create context with timeout to prevent hanging
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	
	resp, err := g.cli.CreateChatCompletion(ctx,
		openai.ChatCompletionRequest{
			Model: openai.GPT4Dot1Nano,
			Messages: []openai.ChatCompletionMessage{
				{Role: "system", Content: g.systemPrompt},
				{Role: "user", Content: q},
			},
		})
	if err != nil {
		return "", err
	}
	if len(resp.Choices) == 0 {
		return "", fmt.Errorf("empty response")
	}
	return resp.Choices[0].Message.Content, nil
}
