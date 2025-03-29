from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    password1 = serializers.CharField(write_only=True, required=False, min_length=5, allow_blank=True)
    password2 = serializers.CharField(write_only=True, required=False, min_length=5, allow_blank=True)
    class Meta:
        model = User
        fields = ['id','email','password1','password2','first_name','last_name','phone_number', 'date_of_birth']
        extra_kwargs = {
            'password1': {'write_only': True, 'min_length': 5},
            'password2': {'write_only': True, 'min_length': 5},
        }

    def create(self, validated_data):
        password1 = validated_data.pop('password1')
        password2 = validated_data.pop('password2')

        if password1 != password2:
            raise serializers.ValidationError("Passwords do not match")

        validated_data['password'] = password1
        return User.objects.create_user(**validated_data)
    
    def update(self, instance, validated_data):
        password1 = validated_data.pop('password1', None)
        password2 = validated_data.pop('password2', None)

        if password1 or password2:
            if password1 != password2:
                raise serializers.ValidationError("Passwords do not match")

        user = super().update(instance, validated_data)
        
        if password1:
            user.set_password(password1)
            user.save()
        
        return user