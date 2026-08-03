package main

import (
	"context"
	"fmt"
	"io"
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
	var result string
	err := g.AskStream(q, func(chunk string) {
		result += chunk
	})
	return result, err
}

func (g *GPT) AskStream(q string, callback func(string)) error {
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	
	models := []string{"gpt-5-nano-2025-08-07", "gpt-5-mini-2025-08-07", "gpt-4o-mini"}
	
	for i, model := range models {
		stream, err := g.cli.CreateChatCompletionStream(ctx, openai.ChatCompletionRequest{
			Model: model,
			Messages: []openai.ChatCompletionMessage{
				{Role: "system", Content: g.systemPrompt},
				{Role: "user", Content: q},
			},
			Stream: true,
		})
		
		if err != nil {
			if i == len(models)-1 {
				return err
			}
			time.Sleep(time.Duration(i+1) * 2 * time.Second)
			continue
		}
		
		defer stream.Close()
		
		for {
			response, err := stream.Recv()
			if err == io.EOF {
				return nil
			}
			if err != nil {
				if i == len(models)-1 {
					return err
				}
				time.Sleep(time.Duration(i+1) * 2 * time.Second)
				break
			}
			
			if len(response.Choices) > 0 && response.Choices[0].Delta.Content != "" {
				callback(response.Choices[0].Delta.Content)
			}
		}
	}
	
	return fmt.Errorf("all models failed")
}
